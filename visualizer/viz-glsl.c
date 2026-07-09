/* viz-glsl — minimal audio-reactive fragment-shader runner for DRM/GBM/GLES2.
 *
 * Purpose-built for the Synchrofazotron visualizer on a Pi Zero 2 W (VC4,
 * OpenGL ES 2.0). Replaces glslViewer: same shader contract, same stdin
 * uniform protocol as glsl-audio-bridge.py ("u_level,0.42" lines at ~43 Hz).
 * The DRM/GBM flow is modeled on kmscube (SetCrtc once, then PageFlip and
 * release the *previous* buffer after each flip - never the one on screen).
 *
 * Build: gcc -O2 -o viz-glsl viz-glsl.c -I/usr/include/libdrm -ldrm -lgbm -lEGL -lGLESv2
 * Usage: viz-glsl shader.frag   (uniforms stream in on stdin, EOF is ignored)
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <signal.h>
#include <time.h>
#include <errno.h>
#include <xf86drm.h>
#include <xf86drmMode.h>
#include <gbm.h>
#include <EGL/egl.h>
#include <GLES2/gl2.h>

static volatile sig_atomic_t running = 1;
static void on_signal(int s) { (void)s; running = 0; }

/* ---- DRM ---------------------------------------------------------- */
static int drm_fd = -1;
static drmModeConnector *conn;
static drmModeModeInfo mode;
static uint32_t crtc_id;
static drmModeCrtc *saved_crtc;

static int drm_init(void) {
    drm_fd = open("/dev/dri/card0", O_RDWR);
    if (drm_fd < 0) { perror("open card0"); return -1; }

    drmModeRes *res = drmModeGetResources(drm_fd);
    if (!res) { perror("GetResources"); return -1; }

    for (int i = 0; i < res->count_connectors; i++) {
        conn = drmModeGetConnector(drm_fd, res->connectors[i]);
        if (conn && conn->connection == DRM_MODE_CONNECTED && conn->count_modes > 0)
            break;
        drmModeFreeConnector(conn); conn = NULL;
    }
    if (!conn) { fprintf(stderr, "no connected connector\n"); return -1; }

    mode = conn->modes[0];                       /* modes[0] = preferred */
    for (int i = 0; i < conn->count_modes; i++)
        if (conn->modes[i].type & DRM_MODE_TYPE_PREFERRED) { mode = conn->modes[i]; break; }

    drmModeEncoder *enc = drmModeGetEncoder(drm_fd, conn->encoder_id);
    if (enc) { crtc_id = enc->crtc_id; drmModeFreeEncoder(enc); }
    if (!crtc_id) {                              /* fall back to the first CRTC */
        drmModeEncoder *e = drmModeGetEncoder(drm_fd, conn->encoders[0]);
        crtc_id = res->crtcs[0];
        if (e) { for (int i = 0; i < res->count_crtcs; i++)
                     if (e->possible_crtcs & (1 << i)) { crtc_id = res->crtcs[i]; break; }
                 drmModeFreeEncoder(e); }
    }
    saved_crtc = drmModeGetCrtc(drm_fd, crtc_id);
    drmModeFreeResources(res);
    fprintf(stderr, "drm: %s %ux%u@%u crtc %u\n",
            conn->modes == NULL ? "?" : mode.name, mode.hdisplay, mode.vdisplay,
            mode.vrefresh, crtc_id);
    return 0;
}

/* ---- GBM + EGL ----------------------------------------------------- */
static struct gbm_device *gbm_dev;
static struct gbm_surface *gbm_surf;
static EGLDisplay egl_dpy;
static EGLSurface egl_surf;

static int egl_init(void) {
    gbm_dev = gbm_create_device(drm_fd);
    gbm_surf = gbm_surface_create(gbm_dev, mode.hdisplay, mode.vdisplay,
                                  GBM_FORMAT_XRGB8888,
                                  GBM_BO_USE_SCANOUT | GBM_BO_USE_RENDERING);
    if (!gbm_surf) { fprintf(stderr, "gbm_surface_create failed\n"); return -1; }

    egl_dpy = eglGetDisplay((EGLNativeDisplayType)gbm_dev);
    if (!eglInitialize(egl_dpy, NULL, NULL)) { fprintf(stderr, "eglInitialize failed\n"); return -1; }
    eglBindAPI(EGL_OPENGL_ES_API);

    static const EGLint cfg_attr[] = {
        EGL_SURFACE_TYPE, EGL_WINDOW_BIT,
        EGL_RED_SIZE, 8, EGL_GREEN_SIZE, 8, EGL_BLUE_SIZE, 8, EGL_ALPHA_SIZE, 0,
        EGL_RENDERABLE_TYPE, EGL_OPENGL_ES2_BIT, EGL_NONE };
    EGLConfig cfgs[64]; EGLint n = 0;
    eglChooseConfig(egl_dpy, cfg_attr, cfgs, 64, &n);
    EGLConfig cfg = NULL;
    for (EGLint i = 0; i < n; i++) {             /* visual must match XRGB8888 */
        EGLint vid;
        if (eglGetConfigAttrib(egl_dpy, cfgs[i], EGL_NATIVE_VISUAL_ID, &vid)
            && vid == GBM_FORMAT_XRGB8888) { cfg = cfgs[i]; break; }
    }
    if (!cfg) { fprintf(stderr, "no XRGB8888 EGL config\n"); return -1; }

    static const EGLint ctx_attr[] = { EGL_CONTEXT_CLIENT_VERSION, 2, EGL_NONE };
    EGLContext ctx = eglCreateContext(egl_dpy, cfg, EGL_NO_CONTEXT, ctx_attr);
    egl_surf = eglCreateWindowSurface(egl_dpy, cfg, (EGLNativeWindowType)gbm_surf, NULL);
    if (ctx == EGL_NO_CONTEXT || egl_surf == EGL_NO_SURFACE ||
        !eglMakeCurrent(egl_dpy, egl_surf, egl_surf, ctx)) {
        fprintf(stderr, "EGL context/surface failed\n"); return -1;
    }
    fprintf(stderr, "gl: %s / %s\n", glGetString(GL_RENDERER), glGetString(GL_VERSION));
    return 0;
}

/* ---- framebuffer bookkeeping (kmscube pattern) --------------------- */
struct fb_entry { struct gbm_bo *bo; uint32_t fb_id; };
static struct fb_entry fbs[8];

static uint32_t fb_for_bo(struct gbm_bo *bo) {
    for (int i = 0; i < 8; i++)
        if (fbs[i].bo == bo) return fbs[i].fb_id;
    uint32_t w = gbm_bo_get_width(bo), h = gbm_bo_get_height(bo);
    uint32_t handles[4] = { gbm_bo_get_handle(bo).u32 };
    uint32_t strides[4] = { gbm_bo_get_stride(bo) };
    uint32_t offsets[4] = { 0 };
    uint32_t fb_id = 0;
    if (drmModeAddFB2(drm_fd, w, h, GBM_FORMAT_XRGB8888, handles, strides, offsets, &fb_id, 0)) {
        perror("AddFB2"); exit(1);
    }
    for (int i = 0; i < 8; i++)
        if (!fbs[i].bo) { fbs[i].bo = bo; fbs[i].fb_id = fb_id; break; }
    return fb_id;
}

static void flip_handler(int fd, unsigned f, unsigned s, unsigned u, void *data)
{ (void)fd; (void)f; (void)s; (void)u; *(int*)data = 0; }

/* ---- shaders -------------------------------------------------------- */
static const char *VERT =
    "attribute vec2 a_pos;\n"
    "void main(){ gl_Position = vec4(a_pos, 0.0, 1.0); }\n";

static GLuint make_shader(GLenum type, const char *src) {
    GLuint sh = glCreateShader(type);
    glShaderSource(sh, 1, &src, NULL);
    glCompileShader(sh);
    GLint ok = 0; glGetShaderiv(sh, GL_COMPILE_STATUS, &ok);
    if (!ok) {
        char log[2048]; glGetShaderInfoLog(sh, sizeof log, NULL, log);
        fprintf(stderr, "shader compile error:\n%s\n", log);
        exit(1);
    }
    return sh;
}

/* ---- stdin uniform protocol ("name,value" per line) ----------------- */
#define N_UNI 4
static const char *uni_names[N_UNI] = { "u_level", "u_bass", "u_mid", "u_treble" };
static float uni_vals[N_UNI];
static char in_buf[512]; static size_t in_len = 0;

static void poll_stdin(void) {
    char tmp[256];
    ssize_t r;
    while ((r = read(0, tmp, sizeof tmp)) > 0) {
        for (ssize_t i = 0; i < r; i++) {
            char c = tmp[i];
            if (c == '\n') {
                in_buf[in_len] = 0; in_len = 0;
                char *comma = strchr(in_buf, ',');
                if (comma) {
                    *comma = 0;
                    for (int u = 0; u < N_UNI; u++)
                        if (!strcmp(in_buf, uni_names[u]))
                            uni_vals[u] = strtof(comma + 1, NULL);
                }
            } else if (in_len < sizeof in_buf - 1)
                in_buf[in_len++] = c;
        }
    }
    /* r == 0 (EOF) or EAGAIN: either way keep rendering */
}

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: %s shader.frag\n", argv[0]); return 1; }

    FILE *f = fopen(argv[1], "rb");
    if (!f) { perror(argv[1]); return 1; }
    static char frag_src[65536];
    frag_src[fread(frag_src, 1, sizeof frag_src - 1, f)] = 0;
    fclose(f);

    signal(SIGINT, on_signal);
    signal(SIGTERM, on_signal);
    fcntl(0, F_SETFL, fcntl(0, F_GETFL) | O_NONBLOCK);

    if (drm_init() || egl_init()) return 1;

    GLuint prog = glCreateProgram();
    glAttachShader(prog, make_shader(GL_VERTEX_SHADER, VERT));
    glAttachShader(prog, make_shader(GL_FRAGMENT_SHADER, frag_src));
    glBindAttribLocation(prog, 0, "a_pos");
    glLinkProgram(prog);
    GLint ok = 0; glGetProgramiv(prog, GL_LINK_STATUS, &ok);
    if (!ok) {
        char log[2048]; glGetProgramInfoLog(prog, sizeof log, NULL, log);
        fprintf(stderr, "link error:\n%s\n", log);
        return 1;
    }
    glUseProgram(prog);

    static const GLfloat quad[] = { -1,-1,  3,-1,  -1,3 };   /* fullscreen tri */
    GLuint vbo; glGenBuffers(1, &vbo);
    glBindBuffer(GL_ARRAY_BUFFER, vbo);
    glBufferData(GL_ARRAY_BUFFER, sizeof quad, quad, GL_STATIC_DRAW);
    glEnableVertexAttribArray(0);
    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, 0);

    GLint loc_res  = glGetUniformLocation(prog, "u_resolution");
    GLint loc_time = glGetUniformLocation(prog, "u_time");
    GLint loc_uni[N_UNI];
    for (int u = 0; u < N_UNI; u++) loc_uni[u] = glGetUniformLocation(prog, uni_names[u]);

    glViewport(0, 0, mode.hdisplay, mode.vdisplay);
    struct timespec t0, t; clock_gettime(CLOCK_MONOTONIC, &t0);

    drmEventContext evctx = { .version = 2, .page_flip_handler = flip_handler };
    struct gbm_bo *bo_prev = NULL;
    int first = 1;
    struct timespec fps_t = t0; int fps_n = 0;   /* fps log (every ~2 s -> stderr) */

    while (running) {
        poll_stdin();
        clock_gettime(CLOCK_MONOTONIC, &t);
        float tt = (t.tv_sec - t0.tv_sec) + (t.tv_nsec - t0.tv_nsec) * 1e-9f;

        fps_n++;
        float fel = (t.tv_sec - fps_t.tv_sec) + (t.tv_nsec - fps_t.tv_nsec) * 1e-9f;
        if (fel >= 2.0f) {
            fprintf(stderr, "viz-glsl: %.1f fps\n", fps_n / fel);
            fps_n = 0; fps_t = t;
        }

        if (loc_res  >= 0) glUniform2f(loc_res, mode.hdisplay, mode.vdisplay);
        if (loc_time >= 0) glUniform1f(loc_time, tt);
        for (int u = 0; u < N_UNI; u++)
            if (loc_uni[u] >= 0) glUniform1f(loc_uni[u], uni_vals[u]);

        glDrawArrays(GL_TRIANGLES, 0, 3);
        eglSwapBuffers(egl_dpy, egl_surf);

        struct gbm_bo *bo = gbm_surface_lock_front_buffer(gbm_surf);
        if (!bo) { fprintf(stderr, "lock_front_buffer failed\n"); break; }
        uint32_t fb_id = fb_for_bo(bo);

        if (first) {
            if (drmModeSetCrtc(drm_fd, crtc_id, fb_id, 0, 0, &conn->connector_id, 1, &mode)) {
                perror("SetCrtc"); break;
            }
            first = 0;
        } else {
            int waiting = 1;
            if (drmModePageFlip(drm_fd, crtc_id, fb_id, DRM_MODE_PAGE_FLIP_EVENT, &waiting)) {
                perror("PageFlip"); break;
            }
            while (waiting && running) {         /* wait on the DRM fd only */
                fd_set fds; FD_ZERO(&fds); FD_SET(drm_fd, &fds);
                struct timeval tv = { 1, 0 };
                int r = select(drm_fd + 1, &fds, NULL, NULL, &tv);
                if (r > 0) drmHandleEvent(drm_fd, &evctx);
                else if (r < 0 && errno != EINTR) { running = 0; }
                else if (r == 0) break;          /* 1 s without vblank: carry on */
            }
        }
        if (bo_prev) gbm_surface_release_buffer(gbm_surf, bo_prev);
        bo_prev = bo;
    }

    /* restore the console */
    if (saved_crtc) {
        drmModeSetCrtc(drm_fd, saved_crtc->crtc_id, saved_crtc->buffer_id,
                       saved_crtc->x, saved_crtc->y, &conn->connector_id, 1, &saved_crtc->mode);
        drmModeFreeCrtc(saved_crtc);
    }
    return 0;
}
