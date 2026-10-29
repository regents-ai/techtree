// A model of the Wallet Bench funding cap: how attempts keep their signed
// sends (platform/lib/techtree/wallet_bench/attempt/changes/sign_funding.ex,
// Funding.admit/1) and how an unknown send is settled from Base
// (Funding.settled/1). It models the design, not the Elixir code.
//
// Each attempt funds its agent with one unit of each token (the USDC and the
// ETH for gas); the run's cap is CAP units of each. A payment is identified by
// (attempt, token): a try that aborts leaves no row, so only one try of an
// attempt can ever keep its payments.
module funding {
  // How many attempts run at once.
  const N_ATTEMPTS: int
  // The run's total, in sends of each token.
  const CAP: int
  // How many times one attempt is retried after it aborts.
  const MAX_RETRIES: int
  // The database isolation level: "read_committed" or "repeatable_read".
  const ISOLATION: str
  // settled/1's order of reads: "nonce_first" (the code) or "receipt_first".
  const SETTLE_ORDER: str
  // Whether a receipt read may come from a node behind the one that answered the nonce read.
  const STALE_RECEIPTS: bool

  type Attempt = int
  type Token = str
  type Pay = (Attempt, Token)

  // An attempt's place in its current try. Prepared: both sends signed, before the
  // transaction. Updated: inside the transaction, its own row updated (under
  // repeatable read this first statement fixes the snapshot). Locked: holds the
  // funder lock. Read: summed the kept payments and found room. Inserted: its
  // payments written, not committed. Committed and Refused are final; Aborted
  // rolls back everything and may retry.
  type Phase = Start | Prepared | Updated | Locked | Read | Inserted | Committed | Aborted | Refused

  // A payment row as committed in the database; NoRow means none is committed.
  type Status = NoRow | Signed | Confirmed | Reverted | Unknown | Replaced

  // What Base did with a committed payment's signed bytes. Displaced: its nonce
  // was used by another transaction, so these bytes can never land.
  type Chain = Pending | IncludedOk | IncludedReverted | Displaced

  // An unknown payment being settled: between settled/1's two reads, holding the first answer.
  type Settle = Idle | FirstRead(bool)

  pure val ATTEMPTS = 1.to(N_ATTEMPTS)
  pure val TOKENS = Set("usdc", "eth")
  pure val PAYS = tuples(ATTEMPTS, TOKENS)
  pure val FREE = 0

  var phase: Attempt -> Phase
  var tries: Attempt -> int
  // The attempt holding pg_advisory_xact_lock for the funder, or FREE.
  var lockHolder: int
  // Under repeatable read, whether the committed payments in each attempt's
  // snapshot (taken at its first statement) leave room for its sends.
  var snapshotRoom: Attempt -> bool
  var status: Pay -> Status
  var chain: Pay -> Chain
  var settle: Pay -> Settle

  // Every send counts except one that moved nothing: reverted, or replaced at its nonce.
  pure def counted(view: Pay -> Status, t: Token): int =
    PAYS.fold(0, (sum, p) => if (p._2 == t and Set(Signed, Confirmed, Unknown).contains(view.get(p))) sum + 1 else sum)

  // within_totals/1 for one more attempt's sends.
  pure def roomFor(view: Pay -> Status): bool =
    TOKENS.forall(t => counted(view, t) + 1 <= CAP)

  pure def paused(view: Pay -> Status): bool =
    PAYS.exists(p => view.get(p) == Unknown)

  // Ghost: the money that really moved on Base.
  def movedOnBase(p: Pay): bool = chain.get(p) == IncludedOk

  def hasReceipt(p: Pay): bool = Set(IncludedOk, IncludedReverted).contains(chain.get(p))

  def nonceUsed(p: Pay): bool = chain.get(p) != Pending

  // ---- attempts --------------------------------------------------------------

  action init = all {
    phase' = ATTEMPTS.mapBy(_ => Start),
    tries' = ATTEMPTS.mapBy(_ => 0),
    lockHolder' = FREE,
    snapshotRoom' = ATTEMPTS.mapBy(_ => true),
    status' = PAYS.mapBy(_ => NoRow),
    chain' = PAYS.mapBy(_ => Pending),
    settle' = PAYS.mapBy(_ => Idle),
  }

  action attemptOnly(newPhase: Attempt -> Phase, newTries: Attempt -> int, newLock: int): bool = all {
    phase' = newPhase,
    tries' = newTries,
    lockHolder' = newLock,
    snapshotRoom' = snapshotRoom,
    status' = status,
    chain' = chain,
    settle' = settle,
  }

  // prepare/1, before any transaction: refuses while paused or when the totals
  // already have no room (read from committed rows), else signs both sends.
  action prepare(a: Attempt): bool = all {
    phase.get(a) == Start,
    attemptOnly(phase.set(a, if (not(paused(status)) and roomFor(status)) Prepared else Refused), tries, lockHolder),
  }

  // The transaction opens and updates the attempt's own row.
  action update(a: Attempt): bool = all {
    phase.get(a) == Prepared,
    phase' = phase.set(a, Updated),
    tries' = tries,
    lockHolder' = lockHolder,
    snapshotRoom' = snapshotRoom.set(a, roomFor(status)),
    status' = status,
    chain' = chain,
    settle' = settle,
  }

  // admit/1: pg_advisory_xact_lock, waiting while another attempt holds it.
  action lock(a: Attempt): bool = all {
    phase.get(a) == Updated,
    lockHolder == FREE,
    attemptOnly(phase.set(a, Locked), tries, a),
  }

  // admit/1: sums every kept payment. Read committed sees what is committed now;
  // repeatable read sees the transaction's snapshot. No room: the step fails and rolls back.
  action read(a: Attempt): bool = {
    val room = if (ISOLATION == "repeatable_read") snapshotRoom.get(a) else roomFor(status)
    all {
      phase.get(a) == Locked,
      if (room)
        attemptOnly(phase.set(a, Read), tries, lockHolder)
      else
        attemptOnly(phase.set(a, Aborted), tries.setBy(a, n => n + 1), FREE),
    }
  }

  action insert(a: Attempt): bool = all {
    phase.get(a) == Read,
    attemptOnly(phase.set(a, Inserted), tries, lockHolder),
  }

  // Commit: the two payments become visible as signed, and the lock is released.
  action commit(a: Attempt): bool = all {
    phase.get(a) == Inserted,
    phase' = phase.set(a, Committed),
    tries' = tries,
    lockHolder' = FREE,
    snapshotRoom' = snapshotRoom,
    status' = TOKENS.fold(status, (s, t) => s.set((a, t), Signed)),
    chain' = chain,
    settle' = settle,
  }

  // Any error before the commit (Base, the database, a crash) rolls the try back.
  action abort(a: Attempt): bool = all {
    Set(Prepared, Updated, Locked, Read, Inserted).contains(phase.get(a)),
    attemptOnly(phase.set(a, Aborted), tries.setBy(a, n => n + 1), if (lockHolder == a) FREE else lockHolder),
  }

  // The Oban retry prepares again from the start.
  action retry(a: Attempt): bool = all {
    phase.get(a) == Aborted,
    tries.get(a) <= MAX_RETRIES,
    attemptOnly(phase.set(a, Start), tries, lockHolder),
  }

  // ---- Base and the payments' outcomes ----------------------------------------

  action chainOnly(newChain: Pay -> Chain): bool = all {
    phase' = phase,
    tries' = tries,
    lockHolder' = lockHolder,
    snapshotRoom' = snapshotRoom,
    status' = status,
    chain' = newChain,
    settle' = settle,
  }

  action statusOnly(newStatus: Pay -> Status, newSettle: Pay -> Settle): bool = all {
    phase' = phase,
    tries' = tries,
    lockHolder' = lockHolder,
    snapshotRoom' = snapshotRoom,
    status' = newStatus,
    chain' = chain,
    settle' = newSettle,
  }

  // A committed payment is broadcast; Base includes it, includes it reverted, or
  // its nonce is used by another transaction. Inclusion is final (no reorgs).
  action land(p: Pay, outcome: Chain): bool = all {
    status.get(p) != NoRow,
    chain.get(p) == Pending,
    chainOnly(chain.set(p, outcome)),
  }

  // receipts/1 finds a receipt for a signed payment.
  action receipt(p: Pay): bool = all {
    status.get(p) == Signed,
    hasReceipt(p),
    statusOnly(status.set(p, if (chain.get(p) == IncludedOk) Confirmed else Reverted), settle),
  }

  // receipts/1 gets no receipt in time (whatever Base has done): the payment is unknown.
  action lose(p: Pay): bool = all {
    status.get(p) == Signed,
    statusOnly(status.set(p, Unknown), settle),
  }

  // settled/1, first read.
  action settleFirst(p: Pay, stale: bool): bool = {
    val firstAnswer = if (SETTLE_ORDER == "nonce_first") nonceUsed(p) else hasReceipt(p) and not(STALE_RECEIPTS and stale)
    all {
      status.get(p) == Unknown,
      settle.get(p) == Idle,
      statusOnly(status, settle.set(p, FirstRead(firstAnswer))),
    }
  }

  // settled/1, second read, then the decision: a receipt decides; no receipt and
  // a used nonce is replaced; otherwise the payment stays unknown.
  action settleSecond(p: Pay, stale: bool): bool = {
    val first = match settle.get(p) {
      | Idle => false
      | FirstRead(answer) => answer
    }
    val receiptSeen = if (SETTLE_ORDER == "nonce_first") hasReceipt(p) and not(STALE_RECEIPTS and stale) else first
    val nonceSeen = if (SETTLE_ORDER == "nonce_first") first else nonceUsed(p)
    val settled =
      if (receiptSeen) (if (chain.get(p) == IncludedOk) Confirmed else Reverted)
      else if (nonceSeen) Replaced
      else Unknown
    all {
      status.get(p) == Unknown,
      settle.get(p) != Idle,
      statusOnly(status.set(p, settled), settle.set(p, Idle)),
    }
  }

  action stutter = all {
    phase' = phase,
    tries' = tries,
    lockHolder' = lockHolder,
    snapshotRoom' = snapshotRoom,
    status' = status,
    chain' = chain,
    settle' = settle,
  }

  action step = {
    nondet a = ATTEMPTS.oneOf()
    nondet p = PAYS.oneOf()
    nondet outcome = Set(IncludedOk, IncludedReverted, Displaced).oneOf()
    nondet stale = Set(true, false).oneOf()
    any {
      prepare(a),
      update(a),
      lock(a),
      read(a),
      insert(a),
      commit(a),
      abort(a),
      retry(a),
      land(p, outcome),
      receipt(p),
      lose(p),
      settleFirst(p, stale),
      settleSecond(p, stale),
      stutter,
    }
  }

  // ---- properties --------------------------------------------------------------

  // 1. Per token, the kept payments that count never pass the cap.
  val CapHolds = TOKENS.forall(t => counted(status, t) <= CAP)

  // 2. Per token, the money that really moved on Base never passes the cap.
  val MoneyCapHolds = TOKENS.forall(t => PAYS.filter(p => p._2 == t and movedOnBase(p)).size() <= CAP)

  // What 2 rests on: a send that landed is never marked replaced.
  val LandedNeverReplaced = PAYS.forall(p => not(movedOnBase(p) and status.get(p) == Replaced))

  val Safe = CapHolds and MoneyCapHolds and LandedNeverReplaced

  // ---- the proof for every depth --------------------------------------------------
  //
  // An inductive invariant for the design as built (read committed, nonce read
  // first, consistent reads): it holds initially and every step keeps it, so it
  // holds in every reachable state however long the run, and it implies Safe.

  // Every variable within its type: the proof starts from any such state.
  val TypeOK = and {
    phase.in(setOfMaps(ATTEMPTS, Set(Start, Prepared, Updated, Locked, Read, Inserted, Committed, Aborted, Refused))),
    tries.in(setOfMaps(ATTEMPTS, 0.to(MAX_RETRIES + 1))),
    lockHolder.in(0.to(N_ATTEMPTS)),
    snapshotRoom.in(setOfMaps(ATTEMPTS, Set(true, false))),
    status.in(setOfMaps(PAYS, Set(NoRow, Signed, Confirmed, Reverted, Unknown, Replaced))),
    chain.in(setOfMaps(PAYS, Set(Pending, IncludedOk, IncludedReverted, Displaced))),
    settle.in(setOfMaps(PAYS, Set(Idle, FirstRead(true), FirstRead(false)))),
  }

  def holdsLock(a: Attempt): bool = Set(Locked, Read, Inserted).contains(phase.get(a))

  // An attempt out of retries stays aborted.
  val RetriesSpent = ATTEMPTS.forall(a => tries.get(a) > MAX_RETRIES implies phase.get(a) == Aborted)

  // Only the lock holder is between the lock and its commit.
  val OneHolder =
    ATTEMPTS.forall(a => holdsLock(a) iff lockHolder == a)

  // An attempt's payments are committed exactly when the attempt is.
  val RowsMatchCommits = PAYS.forall(p => (status.get(p) != NoRow) iff (phase.get(p._1) == Committed))

  // Base and settlement act only on committed payments.
  val ChainOnCommitted = PAYS.forall(p => status.get(p) == NoRow implies (chain.get(p) == Pending and settle.get(p) == Idle))

  // A final status always matches what Base did.
  val StatusMatchesBase = PAYS.forall(p => and {
    status.get(p) == Confirmed implies chain.get(p) == IncludedOk,
    status.get(p) == Reverted implies chain.get(p) == IncludedReverted,
    status.get(p) == Replaced implies chain.get(p) == Displaced,
  })

  // Between settled/1's reads: still unknown, and a used nonce stays used.
  val SettleReads = PAYS.forall(p => settle.get(p) != Idle implies status.get(p) == Unknown) and
    PAYS.forall(p => settle.get(p) == FirstRead(true) implies chain.get(p) != Pending)

  // Under read committed, the room the holder read is still there when it commits:
  // only the holder adds payments, and every other change only removes them from the count.
  val RoomWhileHeld = ATTEMPTS.forall(a => Set(Read, Inserted).contains(phase.get(a)) implies roomFor(status))

  val CodeInductive = and {
    TypeOK,
    RetriesSpent,
    OneHolder,
    RowsMatchCommits,
    ChainOnCommitted,
    StatusMatchesBase,
    SettleReads,
    RoomWhileHeld,
    CapHolds,
  }
}

// The design as built: read committed, nonce read first, one consistent Base node.
module code {
  import funding(
    N_ATTEMPTS = 3, CAP = 2, MAX_RETRIES = 1,
    ISOLATION = "read_committed", SETTLE_ORDER = "nonce_first", STALE_RECEIPTS = false
  ).*

  // Three attempts sign at once; the third finds the cap reached under the lock
  // and rolls back, and its retry is refused before signing.
  run threeAtOnceTest =
    init
      .then(prepare(1)).then(prepare(2)).then(prepare(3))
      .then(update(1)).then(update(2)).then(update(3))
      .then(lock(1)).then(read(1)).then(insert(1)).then(commit(1))
      .then(lock(2)).then(read(2)).then(insert(2)).then(commit(2))
      .then(lock(3)).then(read(3))
      .expect(phase.get(3) == Aborted and lockHolder == FREE and Safe)
      .then(retry(3)).then(prepare(3))
      .expect(phase.get(3) == Refused and Safe)

  // A send lands between settled/1's two reads: the nonce read first saw it
  // unused, so the receipt read decides, and the send is confirmed.
  run landsBetweenReadsTest =
    init
      .then(prepare(1)).then(update(1)).then(lock(1)).then(read(1)).then(insert(1)).then(commit(1))
      .then(prepare(2)).then(update(2)).then(lock(2)).then(read(2)).then(insert(2)).then(commit(2))
      .then(lose((2, "usdc")))
      .then(settleFirst((2, "usdc"), false))
      .then(land((2, "usdc"), IncludedOk))
      .then(settleSecond((2, "usdc"), false))
      .expect(status.get((2, "usdc")) == Confirmed and Safe)
}

// The same design if the database ran repeatable read.
module repeatable_read {
  import funding(
    N_ATTEMPTS = 3, CAP = 2, MAX_RETRIES = 1,
    ISOLATION = "repeatable_read", SETTLE_ORDER = "nonce_first", STALE_RECEIPTS = false
  ).*

  // Each transaction's snapshot is fixed at its own update, before it waits for
  // the lock, so all three see no payments and all three keep their sends.
  run threeAtOnceTest =
    init
      .then(prepare(1)).then(prepare(2)).then(prepare(3))
      .then(update(1)).then(update(2)).then(update(3))
      .then(lock(1)).then(read(1)).then(insert(1)).then(commit(1))
      .then(lock(2)).then(read(2)).then(insert(2)).then(commit(2))
      .then(lock(3)).then(read(3)).then(insert(3)).then(commit(3))
      .expect(not(CapHolds))
}

// settled/1 with its two reads swapped.
module receipt_first {
  import funding(
    N_ATTEMPTS = 3, CAP = 2, MAX_RETRIES = 1,
    ISOLATION = "read_committed", SETTLE_ORDER = "receipt_first", STALE_RECEIPTS = false
  ).*

  // Attempt 2's ETH send reverts. Its USDC send's receipt is read before it
  // lands and its nonce after, so a send that moved is marked replaced, and
  // the room it frees funds a third attempt.
  run landsBetweenReadsTest =
    init
      .then(prepare(1)).then(update(1)).then(lock(1)).then(read(1)).then(insert(1)).then(commit(1))
      .then(prepare(2)).then(update(2)).then(lock(2)).then(read(2)).then(insert(2)).then(commit(2))
      .then(land((1, "usdc"), IncludedOk))
      .then(land((2, "eth"), IncludedReverted)).then(receipt((2, "eth")))
      .then(lose((2, "usdc")))
      .then(settleFirst((2, "usdc"), false))
      .then(land((2, "usdc"), IncludedOk))
      .then(settleSecond((2, "usdc"), false))
      .expect(status.get((2, "usdc")) == Replaced and not(LandedNeverReplaced))
      .then(prepare(3)).then(update(3)).then(lock(3)).then(read(3)).then(insert(3)).then(commit(3))
      .then(land((3, "usdc"), IncludedOk))
      .expect(CapHolds and not(MoneyCapHolds))
}

// The code's order, but the receipt read may reach a node behind the nonce read's.
module stale_receipts {
  import funding(
    N_ATTEMPTS = 3, CAP = 2, MAX_RETRIES = 1,
    ISOLATION = "read_committed", SETTLE_ORDER = "nonce_first", STALE_RECEIPTS = true
  ).*

  // Attempt 2's USDC send lands; the nonce read sees its nonce used, and the
  // receipt read reaches a node that has not seen that block yet, so the send
  // is marked replaced and its room funds a third attempt.
  run laggingNodeTest =
    init
      .then(prepare(1)).then(update(1)).then(lock(1)).then(read(1)).then(insert(1)).then(commit(1))
      .then(prepare(2)).then(update(2)).then(lock(2)).then(read(2)).then(insert(2)).then(commit(2))
      .then(land((1, "usdc"), IncludedOk))
      .then(land((2, "eth"), IncludedReverted)).then(receipt((2, "eth")))
      .then(lose((2, "usdc")))
      .then(land((2, "usdc"), IncludedOk))
      .then(settleFirst((2, "usdc"), false))
      .then(settleSecond((2, "usdc"), true))
      .expect(status.get((2, "usdc")) == Replaced and not(LandedNeverReplaced))
      .then(prepare(3)).then(update(3)).then(lock(3)).then(read(3)).then(insert(3)).then(commit(3))
      .then(land((3, "usdc"), IncludedOk))
      .expect(CapHolds and not(MoneyCapHolds))
}
