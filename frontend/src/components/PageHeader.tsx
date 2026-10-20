import type { ReactNode } from "react";
import { ArrowLeftIcon } from "./Icons";

export function Crumb({ href, children }: { href: string; children: ReactNode }) {
  return (
    <p>
      <a className="crumb" href={href}>
        <ArrowLeftIcon size={15} /> {children}
      </a>
    </p>
  );
}

export default function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        <h1>{title}</h1>
        {subtitle && <p className="subtitle">{subtitle}</p>}
      </div>
      {actions}
    </header>
  );
}
