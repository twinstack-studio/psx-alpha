import Link from "next/link";

export default function NotFound() {
  return (
    <div className="grid min-h-[60vh] place-items-center text-center">
      <div>
        <p className="num text-[56px] font-semibold leading-none" style={{ color: "var(--brand)" }}>404</p>
        <p className="mt-3 text-[15px]">That page is not part of the engine.</p>
        <Link
          href="/"
          className="pill mt-5 inline-flex"
          style={{ color: "var(--text-muted)", background: "var(--surface-2)" }}
        >
          Back to the overview
        </Link>
      </div>
    </div>
  );
}
