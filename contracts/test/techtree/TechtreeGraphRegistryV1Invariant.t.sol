// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {Test} from "forge-std/Test.sol";
import {StdInvariant} from "forge-std/StdInvariant.sol";
import {TechtreeGraphRegistryV1} from "../../src/techtree/TechtreeGraphRegistryV1.sol";

contract TechtreeRegistryHandler is Test {
    TechtreeGraphRegistryV1 public immutable REGISTRY;

    address public immutable REGISTRAR;
    bytes32 public immutable TREE_UID;
    bytes32 public immutable ROOT_UID;
    bytes32 public immutable CHILD_UID;
    bytes32 public immutable THIRD_UID;
    bytes32 public immutable EDGE_UID;

    bool public unauthorizedWriteSucceeded;
    bool public conflictingWriteSucceeded;
    bool public valueSendSucceeded;
    bool public noopRepeatEmittedEvent;
    bool public noopRepeatReverted;
    bytes32 public expectedRootRevision;

    constructor(
        TechtreeGraphRegistryV1 registry_,
        address registrar_,
        bytes32 treeUid_,
        bytes32 rootUid_,
        bytes32 childUid_,
        bytes32 thirdUid_,
        bytes32 edgeUid_
    ) {
        REGISTRY = registry_;
        REGISTRAR = registrar_;
        TREE_UID = treeUid_;
        ROOT_UID = rootUid_;
        CHILD_UID = childUid_;
        THIRD_UID = thirdUid_;
        EDGE_UID = edgeUid_;
        expectedRootRevision = registry_.getNode(rootUid_).revisionUid;
    }

    function unauthorizedTreeWrite(bytes32 uid, address caller) external {
        if (caller == REGISTRAR) caller = address(this);
        if (uid == bytes32(0)) uid = bytes32(uint256(100));
        vm.prank(caller);
        (bool success,) =
            address(REGISTRY).call(abi.encodeCall(TechtreeGraphRegistryV1.registerTree, (uid)));
        if (success) unauthorizedWriteSucceeded = true;
    }

    function unauthorizedNodeWrite(bytes32 uid, address caller) external {
        if (caller == REGISTRAR) caller = address(this);
        if (uid == bytes32(0)) uid = bytes32(uint256(101));
        TechtreeGraphRegistryV1.RecordedPublisher memory publisher =
            TechtreeGraphRegistryV1.RecordedPublisher({
                registry: caller, agentId: uid, tokenId: uint256(uid)
            });
        vm.prank(caller);
        (bool success,) = address(REGISTRY)
            .call(
                abi.encodeCall(
                    TechtreeGraphRegistryV1.registerNode,
                    (
                        uid,
                        bytes32(uint256(103)),
                        TREE_UID,
                        bytes32(0),
                        bytes32(uint256(15)),
                        publisher
                    )
                )
            );
        if (success) unauthorizedWriteSucceeded = true;
    }

    function unauthorizedRevisionWrite(bytes32 revisionUid, address caller) external {
        if (caller == REGISTRAR) caller = address(this);
        if (revisionUid == bytes32(0)) revisionUid = bytes32(uint256(104));
        vm.prank(caller);
        (bool success,) = address(REGISTRY)
            .call(
                abi.encodeCall(
                    TechtreeGraphRegistryV1.registerNodeRevision, (ROOT_UID, revisionUid)
                )
            );
        if (success) unauthorizedWriteSucceeded = true;
    }

    function unauthorizedEdgeWrite(bytes32 uid, address caller) external {
        if (caller == REGISTRAR) caller = address(this);
        if (uid == bytes32(0)) uid = bytes32(uint256(102));
        vm.prank(caller);
        (bool success,) = address(REGISTRY)
            .call(
                abi.encodeCall(
                    TechtreeGraphRegistryV1.registerEdge,
                    (uid, ROOT_UID, CHILD_UID, TechtreeGraphRegistryV1.EdgeKind.DERIVED_FROM)
                )
            );
        if (success) unauthorizedWriteSucceeded = true;
    }

    function retryRegisteredRecords() external {
        TechtreeGraphRegistryV1.NodeRecord memory root = REGISTRY.getNode(ROOT_UID);
        TechtreeGraphRegistryV1.EdgeRecord memory edge = REGISTRY.getEdge(EDGE_UID);
        vm.recordLogs();
        vm.startPrank(REGISTRAR);
        (bool treeSuccess,) =
            address(REGISTRY).call(abi.encodeCall(TechtreeGraphRegistryV1.registerTree, (TREE_UID)));
        (bool nodeSuccess,) = address(REGISTRY)
            .call(
                abi.encodeCall(
                    TechtreeGraphRegistryV1.registerNode,
                    (
                        root.nodeUid,
                        root.revisionUid,
                        root.treeUid,
                        root.parentNodeUid,
                        root.nodeKind,
                        root.recordedPublisher
                    )
                )
            );
        (bool edgeSuccess,) = address(REGISTRY)
            .call(
                abi.encodeCall(
                    TechtreeGraphRegistryV1.registerEdge,
                    (edge.edgeUid, edge.fromNodeUid, edge.toNodeUid, edge.kind)
                )
            );
        vm.stopPrank();
        _recordNoopResult(treeSuccess && nodeSuccess && edgeSuccess);
    }

    function tryConflictingNodeWrite(bytes32 differentKind) external {
        TechtreeGraphRegistryV1.NodeRecord memory root = REGISTRY.getNode(ROOT_UID);
        if (differentKind == root.nodeKind) differentKind = bytes32(uint256(999));
        vm.prank(REGISTRAR);
        (bool success,) = address(REGISTRY)
            .call(
                abi.encodeCall(
                    TechtreeGraphRegistryV1.registerNode,
                    (
                        root.nodeUid,
                        root.revisionUid,
                        root.treeUid,
                        root.parentNodeUid,
                        differentKind,
                        root.recordedPublisher
                    )
                )
            );
        if (success) conflictingWriteSucceeded = true;
    }

    function updateRootRevision(bytes32 revisionUid) external {
        if (revisionUid == bytes32(0)) revisionUid = bytes32(uint256(105));
        vm.prank(REGISTRAR);
        (bool success,) = address(REGISTRY)
            .call(
                abi.encodeCall(
                    TechtreeGraphRegistryV1.registerNodeRevision, (ROOT_UID, revisionUid)
                )
            );
        if (success) expectedRootRevision = revisionUid;
    }

    function retireSeedTree() external {
        vm.prank(REGISTRAR);
        try REGISTRY.retireTree(TREE_UID) {} catch {}
    }

    function retractSeedRoot() external {
        vm.prank(REGISTRAR);
        try REGISTRY.retractNode(ROOT_UID) {} catch {}
    }

    function supersedeSeedRoot() external {
        vm.prank(REGISTRAR);
        try REGISTRY.supersedeNode(ROOT_UID, CHILD_UID) {} catch {}
    }

    function supersedeSeedChild() external {
        vm.prank(REGISTRAR);
        try REGISTRY.supersedeNode(CHILD_UID, THIRD_UID) {} catch {}
    }

    function supersedeSeedThird() external {
        vm.prank(REGISTRAR);
        try REGISTRY.supersedeNode(THIRD_UID, ROOT_UID) {} catch {}
    }

    function selfSupersedeSeedNode(uint8 selector) external {
        bytes32 nodeUid = selector % 3 == 0 ? ROOT_UID : selector % 3 == 1 ? CHILD_UID : THIRD_UID;
        vm.prank(REGISTRAR);
        try REGISTRY.supersedeNode(nodeUid, nodeUid) {} catch {}
    }

    function retractSeedEdge() external {
        vm.prank(REGISTRAR);
        try REGISTRY.retractEdge(EDGE_UID) {} catch {}
    }

    function repeatTreeRetirement() external {
        vm.prank(REGISTRAR);
        try REGISTRY.retireTree(TREE_UID) {} catch {}
        vm.recordLogs();
        vm.prank(REGISTRAR);
        (bool success,) =
            address(REGISTRY).call(abi.encodeCall(TechtreeGraphRegistryV1.retireTree, (TREE_UID)));
        _recordNoopResult(success);
    }

    function repeatRootTerminalStatus() external {
        TechtreeGraphRegistryV1.NodeRecord memory root = REGISTRY.getNode(ROOT_UID);
        if (root.status == TechtreeGraphRegistryV1.NodeStatus.PUBLISHED) {
            vm.prank(REGISTRAR);
            REGISTRY.retractNode(ROOT_UID);
            root = REGISTRY.getNode(ROOT_UID);
        }

        vm.recordLogs();
        vm.prank(REGISTRAR);
        bool success;
        if (root.status == TechtreeGraphRegistryV1.NodeStatus.RETRACTED) {
            (success,) = address(REGISTRY)
                .call(abi.encodeCall(TechtreeGraphRegistryV1.retractNode, (ROOT_UID)));
        } else {
            (success,) = address(REGISTRY)
                .call(
                    abi.encodeCall(
                        TechtreeGraphRegistryV1.supersedeNode, (ROOT_UID, root.supersededBy)
                    )
                );
        }
        _recordNoopResult(success);
    }

    function repeatPublishedRootRevision() external {
        TechtreeGraphRegistryV1.NodeRecord memory root = REGISTRY.getNode(ROOT_UID);
        if (root.status != TechtreeGraphRegistryV1.NodeStatus.PUBLISHED) return;

        vm.recordLogs();
        vm.prank(REGISTRAR);
        (bool success,) = address(REGISTRY)
            .call(
                abi.encodeCall(
                    TechtreeGraphRegistryV1.registerNodeRevision, (ROOT_UID, root.revisionUid)
                )
            );
        _recordNoopResult(success);
    }

    function repeatAvailableSupersession() external {
        bytes32 nodeUid;
        bytes32 successorUid;
        if (
            REGISTRY.getNode(ROOT_UID).status == TechtreeGraphRegistryV1.NodeStatus.PUBLISHED
                && REGISTRY.getNode(CHILD_UID).status
                    == TechtreeGraphRegistryV1.NodeStatus.PUBLISHED
        ) {
            nodeUid = ROOT_UID;
            successorUid = CHILD_UID;
        } else if (
            REGISTRY.getNode(CHILD_UID).status == TechtreeGraphRegistryV1.NodeStatus.PUBLISHED
                && REGISTRY.getNode(THIRD_UID).status
                    == TechtreeGraphRegistryV1.NodeStatus.PUBLISHED
        ) {
            nodeUid = CHILD_UID;
            successorUid = THIRD_UID;
        } else if (
            REGISTRY.getNode(THIRD_UID).status == TechtreeGraphRegistryV1.NodeStatus.PUBLISHED
                && REGISTRY.getNode(ROOT_UID).status == TechtreeGraphRegistryV1.NodeStatus.PUBLISHED
        ) {
            nodeUid = THIRD_UID;
            successorUid = ROOT_UID;
        } else {
            return;
        }

        vm.prank(REGISTRAR);
        REGISTRY.supersedeNode(nodeUid, successorUid);
        vm.recordLogs();
        vm.prank(REGISTRAR);
        (bool success,) = address(REGISTRY)
            .call(abi.encodeCall(TechtreeGraphRegistryV1.supersedeNode, (nodeUid, successorUid)));
        _recordNoopResult(success);
    }

    function repeatEdgeRetraction() external {
        vm.prank(REGISTRAR);
        try REGISTRY.retractEdge(EDGE_UID) {} catch {}
        vm.recordLogs();
        vm.prank(REGISTRAR);
        (bool success,) =
            address(REGISTRY).call(abi.encodeCall(TechtreeGraphRegistryV1.retractEdge, (EDGE_UID)));
        _recordNoopResult(success);
    }

    function trySendValue(uint96 amount) external {
        amount = uint96(bound(amount, 1, 100 ether));
        vm.deal(address(this), amount);
        (bool success,) = address(REGISTRY).call{value: amount}("");
        if (success) valueSendSucceeded = true;
    }

    function _recordNoopResult(bool success) private {
        if (!success) noopRepeatReverted = true;
        if (vm.getRecordedLogs().length != 0) noopRepeatEmittedEvent = true;
    }
}

contract TechtreeGraphRegistryV1InvariantTest is StdInvariant, Test {
    TechtreeGraphRegistryV1 internal registry;
    TechtreeRegistryHandler internal handler;

    address internal constant OWNER = address(0xA11CE);
    address internal constant REGISTRAR = address(0xB0B);
    bytes32 internal constant TREE = bytes32(uint256(1));
    bytes32 internal constant ROOT = bytes32(uint256(2));
    bytes32 internal constant CHILD = bytes32(uint256(3));
    bytes32 internal constant EDGE = bytes32(uint256(4));
    bytes32 internal constant REVISION = bytes32(uint256(5));
    bytes32 internal constant CHILD_REVISION = bytes32(uint256(6));
    bytes32 internal constant THIRD = bytes32(uint256(7));
    bytes32 internal constant THIRD_REVISION = bytes32(uint256(8));
    bytes32 internal constant KIND = bytes32(uint256(11));

    function setUp() public {
        registry = new TechtreeGraphRegistryV1(OWNER, REGISTRAR);
        TechtreeGraphRegistryV1.RecordedPublisher memory publisher =
            TechtreeGraphRegistryV1.RecordedPublisher({
                registry: address(0x1234), agentId: bytes32(uint256(14)), tokenId: 7
            });
        vm.startPrank(REGISTRAR);
        registry.registerTree(TREE);
        registry.registerNode(ROOT, REVISION, TREE, bytes32(0), KIND, publisher);
        registry.registerNode(CHILD, CHILD_REVISION, TREE, ROOT, KIND, publisher);
        registry.registerNode(THIRD, THIRD_REVISION, TREE, CHILD, KIND, publisher);
        registry.registerEdge(EDGE, ROOT, CHILD, TechtreeGraphRegistryV1.EdgeKind.DERIVED_FROM);
        vm.stopPrank();

        handler = new TechtreeRegistryHandler(registry, REGISTRAR, TREE, ROOT, CHILD, THIRD, EDGE);
        targetContract(address(handler));
    }

    function invariantOnlyRegistrarWritesRecords() public view {
        assertFalse(handler.unauthorizedWriteSucceeded());
        assertFalse(handler.conflictingWriteSucceeded());
    }

    function invariantImmutableRecordFieldsNeverChange() public view {
        TechtreeGraphRegistryV1.TreeRecord memory tree = registry.getTree(TREE);
        TechtreeGraphRegistryV1.NodeRecord memory root = registry.getNode(ROOT);
        TechtreeGraphRegistryV1.NodeRecord memory child = registry.getNode(CHILD);
        TechtreeGraphRegistryV1.NodeRecord memory third = registry.getNode(THIRD);
        TechtreeGraphRegistryV1.EdgeRecord memory edge = registry.getEdge(EDGE);

        assertEq(tree.treeUid, TREE);
        assertEq(root.nodeUid, ROOT);
        assertEq(root.revisionUid, handler.expectedRootRevision());
        assertEq(root.treeUid, TREE);
        assertEq(root.parentNodeUid, bytes32(0));
        assertEq(root.nodeKind, KIND);
        assertEq(root.recordedPublisher.registry, address(0x1234));
        assertEq(root.recordedPublisher.agentId, bytes32(uint256(14)));
        assertEq(root.recordedPublisher.tokenId, 7);
        assertEq(child.nodeUid, CHILD);
        assertEq(child.revisionUid, CHILD_REVISION);
        assertEq(child.treeUid, TREE);
        assertEq(child.parentNodeUid, ROOT);
        assertEq(child.nodeKind, KIND);
        assertEq(third.nodeUid, THIRD);
        assertEq(third.revisionUid, THIRD_REVISION);
        assertEq(third.treeUid, TREE);
        assertEq(third.parentNodeUid, CHILD);
        assertEq(third.nodeKind, KIND);
        assertEq(edge.edgeUid, EDGE);
        assertEq(edge.fromNodeUid, ROOT);
        assertEq(edge.toNodeUid, CHILD);
        assertEq(uint8(edge.kind), uint8(TechtreeGraphRegistryV1.EdgeKind.DERIVED_FROM));
    }

    function invariantOnlyExplicitTransitionsChangeStatuses() public view {
        TechtreeGraphRegistryV1.TreeStatus treeStatus = registry.getTree(TREE).status;
        TechtreeGraphRegistryV1.NodeStatus rootStatus = registry.getNode(ROOT).status;
        TechtreeGraphRegistryV1.NodeStatus childStatus = registry.getNode(CHILD).status;
        TechtreeGraphRegistryV1.NodeStatus thirdStatus = registry.getNode(THIRD).status;
        TechtreeGraphRegistryV1.EdgeStatus edgeStatus = registry.getEdge(EDGE).status;

        assertTrue(
            treeStatus == TechtreeGraphRegistryV1.TreeStatus.ACTIVE
                || treeStatus == TechtreeGraphRegistryV1.TreeStatus.RETIRED
        );
        assertTrue(
            rootStatus == TechtreeGraphRegistryV1.NodeStatus.PUBLISHED
                || rootStatus == TechtreeGraphRegistryV1.NodeStatus.SUPERSEDED
                || rootStatus == TechtreeGraphRegistryV1.NodeStatus.RETRACTED
        );
        assertTrue(
            childStatus == TechtreeGraphRegistryV1.NodeStatus.PUBLISHED
                || childStatus == TechtreeGraphRegistryV1.NodeStatus.SUPERSEDED
                || childStatus == TechtreeGraphRegistryV1.NodeStatus.RETRACTED
        );
        assertTrue(
            thirdStatus == TechtreeGraphRegistryV1.NodeStatus.PUBLISHED
                || thirdStatus == TechtreeGraphRegistryV1.NodeStatus.SUPERSEDED
                || thirdStatus == TechtreeGraphRegistryV1.NodeStatus.RETRACTED
        );
        assertTrue(
            edgeStatus == TechtreeGraphRegistryV1.EdgeStatus.ACTIVE
                || edgeStatus == TechtreeGraphRegistryV1.EdgeStatus.RETRACTED
        );
    }

    function invariantNoPathIncreasesContractBalance() public view {
        assertFalse(handler.valueSendSucceeded());
        assertEq(address(registry).balance, 0);
    }

    function invariantRolesRemainSeparated() public view {
        assertNotEq(registry.owner(), registry.registrar());
        if (registry.pendingOwner() != address(0)) {
            assertNotEq(registry.pendingOwner(), registry.registrar());
        }
    }

    function invariantNoNodeIsItsOwnTransitiveSuccessor() public view {
        _assertNoSupersessionCycle(ROOT);
        _assertNoSupersessionCycle(CHILD);
        _assertNoSupersessionCycle(THIRD);
    }

    function invariantNoopRepeatsSucceedWithoutEvents() public view {
        assertFalse(handler.noopRepeatReverted());
        assertFalse(handler.noopRepeatEmittedEvent());
    }

    function _assertNoSupersessionCycle(bytes32 startNodeUid) private view {
        bytes32 cursor = startNodeUid;
        for (uint256 i; i < 3; ++i) {
            TechtreeGraphRegistryV1.NodeRecord memory record = registry.getNode(cursor);
            if (record.status != TechtreeGraphRegistryV1.NodeStatus.SUPERSEDED) return;
            cursor = record.supersededBy;
            assertNotEq(cursor, startNodeUid);
        }
    }
}
