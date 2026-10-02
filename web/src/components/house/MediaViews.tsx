import type { Media } from '@/api/types'

/** Inline on a laptop; a link on the phone — iOS renders embedded PDFs poorly. */
export function PdfView({ pdf, inline }: { pdf: Media; inline: boolean }) {
  return inline
    ? <iframe title="Salgsopstilling" src={pdf.url} className="h-full min-h-[70dvh] w-full rounded-2xl border bg-card" />
    : <a href={pdf.url} target="_blank" rel="noreferrer" className="block rounded-2xl bg-card p-4 font-bold text-primary">
        Open salgsopstilling (PDF)
      </a>
}

