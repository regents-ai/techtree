/**
 * The marketing pages' motion kit: their moving pictures (`field_hook.ts`),
 * rows that rise in (`reveal.ts`) and figures that count up (`tally.ts`). An
 * opening band's own arrival runs as the page opens (`mountEntrance`);
 * everything else is a hook on the part it moves.
 */
import {MarketingField} from "./field_hook"
import {MarketingStagger} from "./reveal"
import {MarketingTally} from "./tally"

export {mountEntrance} from "./reveal"

export const marketingHooks = {
  MarketingField,
  MarketingStagger,
  MarketingTally,
}
