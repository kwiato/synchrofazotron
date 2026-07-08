// Card header: a title on the left and an optional right-hand slot (a toggle, a
// version pill, …). Wraps the shared .card-head flex row so cards stay uniform.
export function CardHead({ title, children }) {
  return (
    <div class="card-head">
      <h2>{title}</h2>
      {children}
    </div>
  );
}
