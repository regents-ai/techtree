/**
 * The home page's motion kit: its moving pictures (`field_hook.ts`), the
 * hero's Results (`carousel.ts`), figures that count up (`tally.ts`), headings
 * that rise and the Stack's tiles (`reveal.ts`), the statement's cards
 * (`statement.ts`), the product groups' accordions (`accordion.ts`) and the
 * dark band's On-ramp (`draw.ts`). The hero's own arrival runs as the page
 * opens (`mountEntrance`); everything else is a hook on the part it moves.
 */
import {MarketingAccordion} from "./accordion"
import {MarketingCarousel} from "./carousel"
import {MarketingDraw} from "./draw"
import {MarketingField} from "./field_hook"
import {MarketingRise, MarketingStagger} from "./reveal"
import {MarketingCards} from "./statement"
import {MarketingTally} from "./tally"

export {mountEntrance} from "./reveal"

export const marketingHooks = {
  MarketingAccordion,
  MarketingCards,
  MarketingCarousel,
  MarketingDraw,
  MarketingField,
  MarketingRise,
  MarketingStagger,
  MarketingTally,
}
