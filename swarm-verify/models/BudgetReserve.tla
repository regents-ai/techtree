---- MODULE BudgetReserve ----
(***************************************************************************)
(* A shared spending limit, used by agents that hold tasks under leases.   *)
(*                                                                         *)
(* The leases are TaskLease's, with the fenced commit. Each task's work    *)
(* costs one unit of a shared budget of Limit units. Under its lease an    *)
(* agent reserves the unit, spends it on the paid step of the work (a      *)
(* model call, an email), commits its result, and gives back what is left. *)
(* The reply to any budget call can be lost, and the agent then sends the  *)
(* same call again; an agent can also pause or crash between any two steps.*)
(*                                                                         *)
(* Three rules decide whether the budget stays right. Each is a constant,  *)
(* TRUE in the repaired design:                                            *)
(*   AtomicAdmit      the budget is checked and the reservation written in *)
(*                    one step; FALSE: two steps, check then reserve.      *)
(*   Idempotent       a call is keyed by its lease (task and epoch): a     *)
(*                    repeated reserve returns the reservation the lease   *)
(*                    already holds, a repeated spend the earlier receipt; *)
(*                    FALSE: every call is a new reservation or a new spend.*)
(*   ReleaseOnExpiry  the step that expires a lease also gives back its    *)
(*                    reservation; FALSE: only its agent can give it back. *)
(*                                                                         *)
(* The budget store and the lease store are one service, so every step     *)
(* below is one transaction of it, and it refuses a budget call under a    *)
(* lease that has ended.                                                   *)
(***************************************************************************)
EXTENDS Naturals

CONSTANTS NumAgents, NumTasks, MaxEpoch, Limit, AtomicAdmit, Idempotent, ReleaseOnExpiry

VARIABLES
  epoch, live, held, result, newest,  \* the leases and results, exactly as in TaskLease
  stage,  \* stage[a]: how far agent a got under the lease it holds:
          \* "idle", "claimed", "checked" (budget seen to have room), "reserved", "paid"
  res,    \* res[t][e]: reservations held under lease e of task t, one unit each
  paid    \* paid[t][e]: times the paid step ran under lease e of task t, one unit each

Lease == INSTANCE TaskLease WITH Fenced <- TRUE

Agents == Lease!Agents
Tasks == Lease!Tasks
Epochs == 1..MaxEpoch
NoLease == Lease!NoLease

leaseVars == <<epoch, live, held, result, newest>>
vars == <<epoch, live, held, result, newest, stage, res, paid>>

\* f[1] + ... + f[n]
RECURSIVE Sum(_, _)
Sum(f, n) == IF n = 0 THEN 0 ELSE f[n] + Sum(f, n - 1)

\* Units held by every reservation, or spent by every paid step, over all leases.
Units(f) == Sum([t \in Tasks |-> Sum(f[t], MaxEpoch)], NumTasks)

TypeOK ==
  /\ Lease!TypeOK
  /\ stage \in [Agents -> {"idle", "claimed", "checked", "reserved", "paid"}]
  /\ res \in [Tasks -> [Epochs -> 0..Limit]]
  /\ paid \in [Tasks -> [Epochs -> 0..Limit]]

Init ==
  /\ Lease!Init
  /\ stage = [a \in Agents |-> "idle"]
  /\ res = [t \in Tasks |-> [e \in Epochs |-> 0]]
  /\ paid = [t \in Tasks |-> [e \in Epochs |-> 0]]

\* Agent a holds its task's newest lease, and the lease has not ended.
LeaseOut(a) ==
  /\ held[a] /= NoLease
  /\ held[a].epoch = epoch[held[a].task]
  /\ live[held[a].task]

Room == Units(res) + Units(paid) < Limit

\* The lease steps, with the budget each one touches.

Claim(a, t) ==
  /\ Lease!Claim(a, t)
  /\ stage' = [stage EXCEPT ![a] = "claimed"]
  /\ UNCHANGED <<res, paid>>

Expire(t) ==
  /\ Lease!Expire(t)
  /\ res' = IF ReleaseOnExpiry THEN [res EXCEPT ![t][epoch[t]] = 0] ELSE res
  /\ UNCHANGED <<stage, paid>>

\* The result is written, the lease ends, and whatever it still reserved goes back.
Commit(a) ==
  /\ stage[a] = "paid"
  /\ Lease!Commit(a)
  /\ res' = [res EXCEPT ![held[a].task][held[a].epoch] = 0]
  /\ stage' = [stage EXCEPT ![a] = "idle"]
  /\ UNCHANGED paid

Reject(a) ==
  /\ stage[a] = "paid"
  /\ Lease!Reject(a)
  /\ stage' = [stage EXCEPT ![a] = "idle"]
  /\ UNCHANGED <<res, paid>>

\* Agent a gives back its lease and every reservation made under it.
Release(a) ==
  /\ Lease!Release(a)
  /\ res' = [res EXCEPT ![held[a].task][held[a].epoch] = 0]
  /\ stage' = [stage EXCEPT ![a] = "idle"]
  /\ UNCHANGED paid

Crash(a) ==
  /\ Lease!Crash(a)
  /\ stage' = [stage EXCEPT ![a] = "idle"]
  /\ UNCHANGED <<res, paid>>

\* The budget steps.

\* Only when AtomicAdmit is FALSE: the service reads the budget and sees room. The
\* reservation is written in a later, separate step.
Check(a) ==
  /\ ~AtomicAdmit
  /\ stage[a] = "claimed"
  /\ LeaseOut(a)
  /\ Room
  /\ stage' = [stage EXCEPT ![a] = "checked"]
  /\ UNCHANGED <<leaseVars, res, paid>>

\* The service reserves one unit under agent a's lease.
Reserve(a) ==
  /\ stage[a] = IF AtomicAdmit THEN "claimed" ELSE "checked"
  /\ LeaseOut(a)
  /\ LET t == held[a].task
         e == held[a].epoch
     IN IF Idempotent /\ res[t][e] > 0
        THEN UNCHANGED res
        ELSE /\ AtomicAdmit => Room
             /\ res' = [res EXCEPT ![t][e] = @ + 1]
  /\ stage' = [stage EXCEPT ![a] = "reserved"]
  /\ UNCHANGED <<leaseVars, paid>>

\* The paid step runs against a reservation of agent a's lease: one unit moves from
\* reserved to spent.
Spend(a) ==
  /\ stage[a] = "reserved"
  /\ LeaseOut(a)
  /\ LET t == held[a].task
         e == held[a].epoch
     IN IF Idempotent /\ paid[t][e] > 0
        THEN UNCHANGED <<res, paid>>
        ELSE /\ res[t][e] > 0
             /\ res' = [res EXCEPT ![t][e] = @ - 1]
             /\ paid' = [paid EXCEPT ![t][e] = @ + 1]
  /\ stage' = [stage EXCEPT ![a] = "paid"]
  /\ UNCHANGED leaseVars

\* The reply to agent a's last budget call is lost: the agent believes the call did not
\* happen, and will send it again.
LoseReply(a) ==
  /\ stage[a] \in {"reserved", "paid"}
  /\ stage' = [stage EXCEPT ![a] = IF @ = "reserved" THEN "claimed" ELSE "reserved"]
  /\ UNCHANGED <<leaseVars, res, paid>>

Next ==
  \/ \E a \in Agents, t \in Tasks : Claim(a, t)
  \/ \E t \in Tasks : Expire(t)
  \/ \E a \in Agents :
       \/ Check(a) \/ Reserve(a) \/ Spend(a) \/ LoseReply(a)
       \/ Commit(a) \/ Reject(a) \/ Release(a) \/ Crash(a)

\* Time passes: a lease that stays out eventually expires.
Spec == Init /\ [][Next]_vars /\ \A t \in Tasks : WF_vars(Expire(t))

(***************************************************************************)
(* Properties                                                              *)
(***************************************************************************)

\* Reserved plus spent never exceeds the limit.
WithinLimit == Units(res) + Units(paid) <= Limit

\* A lease holds at most one reservation, and pays for its work at most once.
OnePerLease ==
  \A t \in Tasks, e \in Epochs : res[t][e] <= 1 /\ paid[t][e] <= 1

\* No reservation outlives its lease.
NoReservationOutlivesLease ==
  \A t \in Tasks, e \in Epochs : res[t][e] > 0 => e = epoch[t] /\ live[t]

\* The lease rules of TaskLease still hold with the budget steps added.
LeaseSafe ==
  /\ Lease!OneOwnerPerEpoch
  /\ Lease!NoStaleOverwrite
  /\ Lease!ResultFromCurrentLease

\* Every reservation is eventually spent or given back.
EveryReservationEnds ==
  \A t \in Tasks, e \in Epochs : res[t][e] > 0 ~> res[t][e] = 0

====
