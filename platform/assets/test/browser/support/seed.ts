import {publishResult, seedWalletBench, type RecordedTest} from "./visitor"

// What two files read and no test may make for itself while the others run: one
// published Result (result.spec.ts) and three recorded Wallet Bench tests
// (wallet_bench.spec.ts). Each is written once for the whole walk, after the server
// has started and before any browser opens, and handed to every worker in its
// environment, so every test reads the same records.
export default function seed() {
  process.env.TECHTREE_BROWSER_RESULT = publishResult()
  process.env.TECHTREE_BROWSER_WALLET_BENCH = JSON.stringify(seedWalletBench())
}

// The published Result's fingerprint.
export const publishedResult = (): string => process.env.TECHTREE_BROWSER_RESULT as string

// The recorded Wallet Bench tests, by outcome.
export const recordedTests = (): {passed: RecordedTest; failed: RecordedTest; running: RecordedTest} =>
  JSON.parse(process.env.TECHTREE_BROWSER_WALLET_BENCH as string)
