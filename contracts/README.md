# Techtree registry contracts

Own the Techtree graph registry here alongside the CLI, plugin and platform.
Source, deployment scripts and tests were imported unchanged from Regent Contracts
commit `9ddae75`, whose history is retained as a merge parent. The forge-std gitlink
remains `77041d2ce690e692d6e03cc812b57d1ddaa4d505`.

After materializing the pinned submodule and Solidity 0.8.28, run from this directory:

```sh
forge fmt --check
forge build --offline
forge test --offline
```

Deployment scripts require separate founder authorization. Local tests do not send
transactions to a network. Historical contract analysis remains in Regents' retained
contract evidence; it is not a current Techtree scan.
