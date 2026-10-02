const MAX_LEAD = 160

/** The listing's first line as a headline and the rest as body text; realtor pages lead
 *  with one line like that. A long first line gives up its first sentence; with no usable
 *  first line there is no headline. */
export function splitDescription(text: string): { lead: string | null; rest: string } {
  const lines = text.split('\n')
  const i = lines.findIndex(l => l.trim())
  if (i < 0) return { lead: null, rest: '' }
  let lead = lines[i].trim().replace(/^[-•*]\s*/, '')
  let rest = lines.slice(i + 1).join('\n').trim()
  if (lead.length > MAX_LEAD) {
    const end = lead.indexOf('. ')
    if (end < 0 || end + 1 > MAX_LEAD) return { lead: null, rest: text.trim() }
    rest = `${lead.slice(end + 2)}\n${rest}`.trim()
    lead = lead.slice(0, end + 1)
  }
  return { lead: lead.replace(/\.$/, ''), rest }
}
