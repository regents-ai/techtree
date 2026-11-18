---- MODULE Cancel ----
(***************************************************************************)
(* Cancellation of a parent task and its children.                         *)
(*                                                                         *)
(* A parent task has NumChildren child agents, each working under its own  *)
(* lease and holding its share of the budget until it stops. Children run  *)
(* until told to stop. The parent may cancel at any moment: it records the *)
(* cancellation in the shared store and sends every child a cancel         *)
(* message. A message can be lost.                                         *)
(*                                                                         *)
(* StoreCheck = FALSE: a child stops only when its message arrives (the    *)
(*                     unsafe rule).                                       *)
(* StoreCheck = TRUE:  every step of a child's work, its heartbeat         *)
(*                     included, is a call to the store, which refuses it  *)
(*                     once the cancellation is recorded; a refused child  *)
(*                     stops and gives back its lease and budget, whether  *)
(*                     or not its message arrives.                         *)
(***************************************************************************)
EXTENDS Naturals

CONSTANTS NumChildren, StoreCheck

Children == 1..NumChildren

VARIABLES
  canceled,  \* the parent's cancellation is recorded in the store
  msg,       \* msg[c]: the cancel message to child c: "none" (not sent), "sent", "delivered", "lost"
  running,   \* running[c]: child c is still working and still holds its lease and budget
  late       \* late[c]: child c did a step of work after the cancellation was recorded
             \* (a record kept for the properties; no step reads it)

vars == <<canceled, msg, running, late>>

TypeOK ==
  /\ canceled \in BOOLEAN
  /\ msg \in [Children -> {"none", "sent", "delivered", "lost"}]
  /\ running \in [Children -> BOOLEAN]
  /\ late \in [Children -> BOOLEAN]

Init ==
  /\ canceled = FALSE
  /\ msg = [c \in Children |-> "none"]
  /\ running = [c \in Children |-> TRUE]
  /\ late = [c \in Children |-> FALSE]

\* The parent cancels: the store records it and a message goes to every child.
CancelParent ==
  /\ ~canceled
  /\ canceled' = TRUE
  /\ msg' = [c \in Children |-> "sent"]
  /\ UNCHANGED <<running, late>>

Deliver(c) ==
  /\ msg[c] = "sent"
  /\ msg' = [msg EXCEPT ![c] = "delivered"]
  /\ UNCHANGED <<canceled, running, late>>

Lose(c) ==
  /\ msg[c] = "sent"
  /\ msg' = [msg EXCEPT ![c] = "lost"]
  /\ UNCHANGED <<canceled, running, late>>

\* Child c does a step of its work. With StoreCheck, the store refuses it once the
\* cancellation is recorded.
Work(c) ==
  /\ running[c]
  /\ StoreCheck => ~canceled
  /\ late' = [late EXCEPT ![c] = @ \/ canceled]
  /\ UNCHANGED <<canceled, msg, running>>

\* Child c stops and gives back its lease and budget: its message arrived, or (with
\* StoreCheck) the store refused its last call.
Stop(c) ==
  /\ running[c]
  /\ msg[c] = "delivered" \/ (StoreCheck /\ canceled)
  /\ running' = [running EXCEPT ![c] = FALSE]
  /\ UNCHANGED <<canceled, msg, late>>

Next ==
  \/ CancelParent
  \/ \E c \in Children : Deliver(c) \/ Lose(c) \/ Work(c) \/ Stop(c)

\* A message that is not lost is eventually delivered, and a child able to stop
\* eventually does.
Spec ==
  /\ Init /\ [][Next]_vars
  /\ \A c \in Children : WF_vars(Deliver(c)) /\ WF_vars(Stop(c))

(***************************************************************************)
(* Properties                                                              *)
(***************************************************************************)

\* No child does work after the cancellation is recorded.
NoWorkAfterCancel == \A c \in Children : ~late[c]

\* After a cancellation, every child eventually stops and gives back what it held.
CancelStopsEveryChild == canceled ~> \A c \in Children : ~running[c]

====
