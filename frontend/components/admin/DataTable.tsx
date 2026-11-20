import type { ReactNode } from "react";

export type Column<T> = { header: string; cell: (row: T) => ReactNode; className?: string };

/** Tabla accesible: <caption> para lectores de pantalla y desplazamiento horizontal en móvil. */
export function DataTable<T>({ caption, columns, rows, empty, rowKey }: {
  caption: string; columns: Column<T>[]; rows: T[]; empty: string; rowKey: (r: T) => string;
}) {
  if (rows.length === 0) return <p className="py-6 text-center text-muted">{empty}</p>;
  return (
    <div className="overflow-x-auto rounded-xl border border-line bg-surface-2">
      <table className="min-w-full text-left text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead className="border-b border-line bg-brand-soft">
          <tr>{columns.map((c) => <th key={c.header} scope="col" className="px-4 py-3 font-semibold">{c.header}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={rowKey(r)} className="border-b border-line last:border-0">
              {columns.map((c) => <td key={c.header} className={`px-4 py-3 align-top ${c.className ?? ""}`}>{c.cell(r)}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
