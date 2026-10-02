import { expect, test } from 'vitest'
import { splitDescription } from '@/lib/description'

test('a bulleted first line becomes the headline, without the bullet or the full stop', () => {
  expect(splitDescription('- Stort og lyst køkken-alrum mod vest.\n\n- Lukket have.\nVelkommen.'))
    .toEqual({ lead: 'Stort og lyst køkken-alrum mod vest', rest: '- Lukket have.\nVelkommen.' })
})

test('a long first line gives its first sentence as the headline', () => {
  const first = 'Beliggenheden er som skræddersyet til familien, der ønsker en nem hverdag.'
  const more = ' I bosætter jer i et attraktivt kvarter, hvor I har den smukke natur næsten i baghaven, samtidig med at hverdagens logistik glider let.'
  expect(splitDescription(first + more)).toEqual({ lead: first.slice(0, -1), rest: more.trim() })
})

test('no usable first line: no headline, all of it is body text', () => {
  const long = 'x'.repeat(200)
  expect(splitDescription(long)).toEqual({ lead: null, rest: long })
  expect(splitDescription('  \n ')).toEqual({ lead: null, rest: '' })
})
