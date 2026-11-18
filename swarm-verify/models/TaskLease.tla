---- MODULE TaskLease ----
(***************************************************************************)
(* Task ownership under leases.                                            *)
(*                                                                         *)
(* NumAgents agents take tasks from one shared queue. An agent claims a    *)
(* free task and holds it under a lease. The queue numbers the leases of   *)
(* each task: epoch 1 for the first claim, 2 for the next, and so on, up   *)
(* to MaxEpoch (the task's attempts). A lease can expire at any moment     *)
(* while it is out: that is how the model lets an agent pause (a long      *)
(* garbage collection, a lost network, a slow tool call) for longer than   *)
(* its lease. Another agent may then claim the task under the next epoch.  *)
(* The paused agent is not told: it still believes it holds its lease, and *)
(* may later try to commit its result.                                     *)
(*                                                                         *)
(* Fenced = FALSE: the result store accepts every commit (the unsafe rule).*)
(* Fenced = TRUE:  every commit names the lease it was made under, and the *)
(*                 store accepts it only when that lease is the task's     *)
(*                 newest and has not ended, checked in the same step that *)
(*                 writes the result (the epoch is a fencing token).       *)
(*                                                                         *)
(* The store is one service: each action below is one indivisible step of  *)
(* it (one database transaction). Agents and tasks are numbered from 1; 0  *)
(* means "none".                                                           *)
(***************************************************************************)
EXTENDS Naturals

CONSTANTS NumAgents, NumTasks, MaxEpoch, Fenced

Agents == 1..NumAgents
Tasks == 1..NumTasks

NoLease == [task |-> 0, epoch |-> 0]
NoResult == [agent |-> 0, epoch |-> 0]

VARIABLES
  epoch,   \* epoch[t]: the newest lease the queue granted on task t (0: never claimed)
  live,    \* live[t]: that lease is still out: not expired, not given back
  held,    \* held[a]: the lease agent a believes it holds, or NoLease
  result,  \* result[t]: the result the store holds for task t: who wrote it, under which lease
  newest   \* newest[t]: the newest epoch whose commit the store ever accepted (a record kept
           \* for the properties below; no step reads it)

vars == <<epoch, live, held, result, newest>>

TypeOK ==
  /\ epoch \in [Tasks -> 0..MaxEpoch]
  /\ live \in [Tasks -> BOOLEAN]
  /\ held \in [Agents -> {NoLease} \cup [task : Tasks, epoch : 1..MaxEpoch]]
  /\ result \in [Tasks -> {NoResult} \cup [agent : Agents, epoch : 1..MaxEpoch]]
  /\ newest \in [Tasks -> 0..MaxEpoch]

Init ==
  /\ epoch = [t \in Tasks |-> 0]
  /\ live = [t \in Tasks |-> FALSE]
  /\ held = [a \in Agents |-> NoLease]
  /\ result = [t \in Tasks |-> NoResult]
  /\ newest = [t \in Tasks |-> 0]

\* The commit agent a would make is accepted by the store.
Accepted(a) ==
  \/ ~Fenced
  \/ held[a].epoch = epoch[held[a].task] /\ live[held[a].task]

\* An idle agent claims task t: the task has no result, no lease out, and attempts left.
Claim(a, t) ==
  /\ held[a] = NoLease
  /\ result[t] = NoResult
  /\ ~live[t]
  /\ epoch[t] < MaxEpoch
  /\ epoch' = [epoch EXCEPT ![t] = @ + 1]
  /\ live' = [live EXCEPT ![t] = TRUE]
  /\ held' = [held EXCEPT ![a] = [task |-> t, epoch |-> epoch[t] + 1]]
  /\ UNCHANGED <<result, newest>>

\* Task t's lease runs out. Its holder is not told.
Expire(t) ==
  /\ live[t]
  /\ live' = [live EXCEPT ![t] = FALSE]
  /\ UNCHANGED <<epoch, held, result, newest>>

\* Agent a commits its result and the store accepts it. A commit under the task's newest
\* lease also gives that lease back; a stale one (only possible unfenced) leaves it out.
Commit(a) ==
  /\ held[a] /= NoLease
  /\ Accepted(a)
  /\ LET t == held[a].task
         e == held[a].epoch
     IN /\ result' = [result EXCEPT ![t] = [agent |-> a, epoch |-> e]]
        /\ newest' = [newest EXCEPT ![t] = IF e > @ THEN e ELSE @]
        /\ live' = IF e = epoch[t] THEN [live EXCEPT ![t] = FALSE] ELSE live
  /\ held' = [held EXCEPT ![a] = NoLease]
  /\ UNCHANGED epoch

\* Agent a commits and the store refuses: its lease is not the newest, or has ended.
\* The agent learns it lost the task and drops it.
Reject(a) ==
  /\ held[a] /= NoLease
  /\ ~Accepted(a)
  /\ held' = [held EXCEPT ![a] = NoLease]
  /\ UNCHANGED <<epoch, live, result, newest>>

\* Agent a gives its lease back without a result (it stops, or a step of its work was
\* refused). Giving back a lease that has already been replaced changes nothing in the store.
Release(a) ==
  /\ held[a] /= NoLease
  /\ LET t == held[a].task
     IN live' = IF held[a].epoch = epoch[t] THEN [live EXCEPT ![t] = FALSE] ELSE live
  /\ held' = [held EXCEPT ![a] = NoLease]
  /\ UNCHANGED <<epoch, result, newest>>

\* Agent a crashes and restarts with nothing: it forgets its lease, which runs out later.
Crash(a) ==
  /\ held[a] /= NoLease
  /\ held' = [held EXCEPT ![a] = NoLease]
  /\ UNCHANGED <<epoch, live, result, newest>>

Next ==
  \/ \E a \in Agents, t \in Tasks : Claim(a, t)
  \/ \E t \in Tasks : Expire(t)
  \/ \E a \in Agents : Commit(a) \/ Reject(a) \/ Release(a) \/ Crash(a)

Spec == Init /\ [][Next]_vars

(***************************************************************************)
(* Properties                                                              *)
(***************************************************************************)

\* At most one accepted owner per task epoch: no two agents hold the same lease.
OneOwnerPerEpoch ==
  \A a, b \in Agents : a /= b /\ held[a] /= NoLease => held[a] /= held[b]

\* A stored result is never overwritten by a stale holder: it always comes from the
\* newest lease whose commit the store accepted.
NoStaleOverwrite ==
  \A t \in Tasks : result[t] /= NoResult => result[t].epoch = newest[t]

\* Every task's result comes from its current lease: the newest one the queue granted.
ResultFromCurrentLease ==
  \A t \in Tasks : result[t] /= NoResult => result[t].epoch = epoch[t]

====
