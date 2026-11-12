// Invariant: a page opened while Privy still holds a sign-in signs the person
// back in without a press, and nothing else does. An upgrade that moves Privy's
// keys would quietly stop that, so the installed Privy is read too.
import {readdirSync, readFileSync} from "node:fs"
import {expect, it} from "vitest"

import {privyHoldsSession} from "../js/auth_lazy"

const storage = (entries: Record<string, string>) => ({getItem: (key: string) => entries[key] ?? null})

it("holds a sign-in only when Privy keeps a session, not a connected wallet alone", () => {
  expect(privyHoldsSession(storage({"privy:token": '"t"'}))).toBe(true)
  expect(privyHoldsSession(storage({"privy:refresh_token": '"r"'}))).toBe(true)
  expect(privyHoldsSession(storage({"privy:connections": '[{"address":"0x1111111111111111111111111111111111111111"}]'}))).toBe(false)
  expect(privyHoldsSession(storage({}))).toBe(false)
  expect(privyHoldsSession(null)).toBe(false)
})

it("reads the keys the installed Privy writes", () => {
  const dist = new URL("../node_modules/@privy-io/react-auth/dist/esm/", import.meta.url)
  const source = readdirSync(dist).filter(name => name.endsWith(".mjs"))
    .map(name => readFileSync(new URL(name, dist), "utf8")).join("\n")
  for (const key of ["privy:token", "privy:refresh_token"]) expect(source).toContain(`"${key}"`)
})
