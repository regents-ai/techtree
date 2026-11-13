/**
 * One GPU device for every moving picture of the home page's own (`field.ts`):
 * the first to draw asks for it, the rest draw on it, and the last to go gives
 * it back. Loaded only with the pictures, once one is really going to be shown.
 */
import {init} from "vgpu"
import {shareDevice} from "./shared_device"

export const device = shareDevice(() => init())
