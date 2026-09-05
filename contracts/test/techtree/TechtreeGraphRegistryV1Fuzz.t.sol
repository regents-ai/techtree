// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {Test, Vm} from "forge-std/Test.sol";
import {TechtreeGraphRegistryV1} from "../../src/techtree/TechtreeGraphRegistryV1.sol";

contract TechtreeGraphRegistryV1FuzzTest is Test {
    TechtreeGraphRegistryV1 internal registry;

    address internal constant OWNER = address(0xA11CE);
    address internal constant REGISTRAR = address(0xB0B);

    function setUp() public {
        registry = new TechtreeGraphRegistryV1(OWNER, REGISTRAR);
    }

    function testFuzzNodeRoundTripAndIdempotency(
        bytes32 treeUid,
        bytes32 nodeUid,
        bytes32 revisionUid,
        bytes32 nodeKind,
        address publisherRegistry,
        bytes32 agentId,
        uint256 tokenId
    ) public {
        vm.assume(treeUid != bytes32(0));
        vm.assume(nodeUid != bytes32(0));
        vm.assume(revisionUid != bytes32(0));

        TechtreeGraphRegistryV1.RecordedPublisher memory publisher =
            _publisher(publisherRegistry, agentId, tokenId);
        _registerTree(treeUid);
        _registerNode(nodeUid, revisionUid, treeUid, bytes32(0), nodeKind, publisher);

        TechtreeGraphRegistryV1.NodeRecord memory beforeRecord = registry.getNode(nodeUid);
        vm.recordLogs();
        _registerNode(nodeUid, revisionUid, treeUid, bytes32(0), nodeKind, publisher);
        Vm.Log[] memory logs = vm.getRecordedLogs();
        TechtreeGraphRegistryV1.NodeRecord memory afterRecord = registry.getNode(nodeUid);

        assertEq(logs.length, 0);
        assertEq(abi.encode(beforeRecord), abi.encode(afterRecord));
        assertEq(afterRecord.revisionUid, revisionUid);
        assertEq(afterRecord.treeUid, treeUid);
        assertEq(afterRecord.nodeKind, nodeKind);
        assertEq(afterRecord.recordedPublisher.registry, publisherRegistry);
        assertEq(afterRecord.recordedPublisher.agentId, agentId);
        assertEq(afterRecord.recordedPublisher.tokenId, tokenId);
    }

    function testFuzzNodeUidCollisionRejectsDifferentTuple(
        bytes32 treeUid,
        bytes32 nodeUid,
        bytes32 revisionUid,
        bytes32 nodeKind,
        address publisherRegistry,
        bytes32 agentId,
        uint256 tokenId,
        uint256 differentTokenId
    ) public {
        vm.assume(treeUid != bytes32(0));
        vm.assume(nodeUid != bytes32(0));
        vm.assume(revisionUid != bytes32(0));
        vm.assume(tokenId != differentTokenId);

        _registerTree(treeUid);
        _registerNode(
            nodeUid,
            revisionUid,
            treeUid,
            bytes32(0),
            nodeKind,
            _publisher(publisherRegistry, agentId, tokenId)
        );
        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.RecordConflict.selector, nodeUid)
        );
        _registerNode(
            nodeUid,
            revisionUid,
            treeUid,
            bytes32(0),
            nodeKind,
            _publisher(publisherRegistry, agentId, differentTokenId)
        );

        assertEq(registry.getNode(nodeUid).recordedPublisher.tokenId, tokenId);
    }

    function testFuzzNodeBatchRoundTrip(
        bytes32 seed,
        uint8 requestedLength,
        bytes32 nodeKind,
        address publisherRegistry,
        bytes32 agentId,
        uint256 tokenId
    ) public {
        uint256 length = bound(requestedLength, 1, 20);
        bytes32 treeUid = _nonzeroUid(seed, 0);
        _registerTree(treeUid);

        TechtreeGraphRegistryV1.NodeInput[] memory inputs =
            new TechtreeGraphRegistryV1.NodeInput[](length);
        bytes32 previous;
        for (uint256 i; i < length; ++i) {
            bytes32 nodeUid = _nonzeroUid(seed, i + 1);
            inputs[i] = TechtreeGraphRegistryV1.NodeInput({
                nodeUid: nodeUid,
                revisionUid: _nonzeroUid(seed, i + 100),
                treeUid: treeUid,
                parentNodeUid: previous,
                nodeKind: nodeKind,
                recordedPublisher: _publisher(publisherRegistry, agentId, _add(tokenId, i))
            });
            previous = nodeUid;
        }

        vm.prank(REGISTRAR);
        registry.registerNodes(inputs);
        for (uint256 i; i < length; ++i) {
            TechtreeGraphRegistryV1.NodeRecord memory record = registry.getNode(inputs[i].nodeUid);
            assertEq(record.treeUid, treeUid);
            assertEq(record.revisionUid, inputs[i].revisionUid);
            assertEq(record.parentNodeUid, inputs[i].parentNodeUid);
            assertEq(record.recordedPublisher.tokenId, _add(tokenId, i));
        }

        vm.recordLogs();
        vm.prank(REGISTRAR);
        registry.registerNodes(inputs);
        assertEq(vm.getRecordedLogs().length, 0);
    }

    function testFuzzEdgeRoundTripAndIdempotency(bytes32 seed, bytes32 edgeUid, uint8 rawKind)
        public
    {
        vm.assume(edgeUid != bytes32(0));
        TechtreeGraphRegistryV1.EdgeKind kind =
            TechtreeGraphRegistryV1.EdgeKind(bound(rawKind, 0, 5));
        (bytes32 root, bytes32 child) = _seedNodes(seed);

        _registerEdge(edgeUid, root, child, kind);
        TechtreeGraphRegistryV1.EdgeRecord memory beforeRecord = registry.getEdge(edgeUid);
        vm.recordLogs();
        _registerEdge(edgeUid, root, child, kind);
        TechtreeGraphRegistryV1.EdgeRecord memory afterRecord = registry.getEdge(edgeUid);

        assertEq(vm.getRecordedLogs().length, 0);
        assertEq(abi.encode(beforeRecord), abi.encode(afterRecord));
        assertEq(uint8(afterRecord.kind), uint8(kind));
    }

    function testFuzzEdgeBatchRoundTrip(bytes32 seed, uint8 requestedLength, uint8 rawKind) public {
        uint256 length = bound(requestedLength, 1, 20);
        TechtreeGraphRegistryV1.EdgeKind kind =
            TechtreeGraphRegistryV1.EdgeKind(bound(rawKind, 0, 5));
        (bytes32 root, bytes32 child) = _seedNodes(seed);
        TechtreeGraphRegistryV1.EdgeInput[] memory inputs =
            new TechtreeGraphRegistryV1.EdgeInput[](length);
        for (uint256 i; i < length; ++i) {
            inputs[i] = TechtreeGraphRegistryV1.EdgeInput({
                edgeUid: _nonzeroUid(seed, i + 10), fromNodeUid: root, toNodeUid: child, kind: kind
            });
        }

        vm.prank(REGISTRAR);
        registry.registerEdges(inputs);
        for (uint256 i; i < length; ++i) {
            TechtreeGraphRegistryV1.EdgeRecord memory record = registry.getEdge(inputs[i].edgeUid);
            assertEq(record.fromNodeUid, root);
            assertEq(record.toNodeUid, child);
            assertEq(uint8(record.kind), uint8(kind));
        }

        vm.recordLogs();
        vm.prank(REGISTRAR);
        registry.registerEdges(inputs);
        assertEq(vm.getRecordedLogs().length, 0);
    }

    function testFuzzFailingBatchDoesNotCorruptState(bytes32 seed, bytes32 missingParent) public {
        bytes32 treeUid = _nonzeroUid(seed, 0);
        bytes32 firstNode = _nonzeroUid(seed, 1);
        bytes32 secondNode = _nonzeroUid(seed, 2);
        vm.assume(missingParent != bytes32(0));
        vm.assume(missingParent != firstNode);
        _registerTree(treeUid);

        TechtreeGraphRegistryV1.NodeInput[] memory inputs =
            new TechtreeGraphRegistryV1.NodeInput[](2);
        inputs[0] = TechtreeGraphRegistryV1.NodeInput({
            nodeUid: firstNode,
            revisionUid: _nonzeroUid(seed, 100),
            treeUid: treeUid,
            parentNodeUid: bytes32(0),
            nodeKind: seed,
            recordedPublisher: _publisher(address(1), seed, 1)
        });
        inputs[1] = TechtreeGraphRegistryV1.NodeInput({
            nodeUid: secondNode,
            revisionUid: _nonzeroUid(seed, 101),
            treeUid: treeUid,
            parentNodeUid: missingParent,
            nodeKind: seed,
            recordedPublisher: _publisher(address(2), seed, 2)
        });

        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.RecordNotFound.selector, missingParent)
        );
        vm.prank(REGISTRAR);
        registry.registerNodes(inputs);
        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.RecordNotFound.selector, firstNode)
        );
        registry.getNode(firstNode);
    }

    function testFuzzConstructorRejectsSameRole(address role) public {
        vm.assume(role != address(0));
        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.RoleCollision.selector, role)
        );
        new TechtreeGraphRegistryV1(role, role);
    }

    function testFuzzRevisionUpdateAndTerminalRestriction(
        bytes32 seed,
        bytes32 initialRevisionUid,
        bytes32 newRevisionUid,
        bool supersede
    ) public {
        vm.assume(initialRevisionUid != bytes32(0));
        vm.assume(newRevisionUid != bytes32(0));
        vm.assume(initialRevisionUid != newRevisionUid);

        bytes32 treeUid = _nonzeroUid(seed, 0);
        bytes32 root = _nonzeroUid(seed, 1);
        bytes32 child = _nonzeroUid(seed, 2);
        _registerTree(treeUid);
        _registerNode(
            root, initialRevisionUid, treeUid, bytes32(0), seed, _publisher(address(1), seed, 1)
        );
        _registerNode(
            child, _nonzeroUid(seed, 3), treeUid, root, seed, _publisher(address(2), seed, 2)
        );

        vm.prank(REGISTRAR);
        registry.registerNodeRevision(root, newRevisionUid);
        assertEq(registry.getNode(root).revisionUid, newRevisionUid);

        vm.recordLogs();
        vm.prank(REGISTRAR);
        registry.registerNodeRevision(root, newRevisionUid);
        assertEq(vm.getRecordedLogs().length, 0);

        TechtreeGraphRegistryV1.NodeStatus terminalStatus;
        vm.prank(REGISTRAR);
        if (supersede) {
            registry.supersedeNode(root, child);
            terminalStatus = TechtreeGraphRegistryV1.NodeStatus.SUPERSEDED;
        } else {
            registry.retractNode(root);
            terminalStatus = TechtreeGraphRegistryV1.NodeStatus.RETRACTED;
        }
        vm.expectRevert(
            abi.encodeWithSelector(
                TechtreeGraphRegistryV1.RevisionUpdateNotAllowed.selector, root, terminalStatus
            )
        );
        vm.prank(REGISTRAR);
        registry.registerNodeRevision(root, newRevisionUid);
    }

    function testFuzzTerminalRepeatsEmitNoEvents(bytes32 seed, bool supersede) public {
        (bytes32 root, bytes32 child) = _seedNodes(seed);
        bytes32 treeUid = registry.getNode(root).treeUid;
        bytes32 edgeUid = _nonzeroUid(seed, 10);
        _registerEdge(edgeUid, root, child, TechtreeGraphRegistryV1.EdgeKind.DERIVED_FROM);

        vm.startPrank(REGISTRAR);
        registry.retireTree(treeUid);
        vm.recordLogs();
        registry.retireTree(treeUid);
        assertEq(vm.getRecordedLogs().length, 0);

        registry.retractEdge(edgeUid);
        vm.recordLogs();
        registry.retractEdge(edgeUid);
        assertEq(vm.getRecordedLogs().length, 0);

        if (supersede) {
            registry.supersedeNode(root, child);
            vm.recordLogs();
            registry.supersedeNode(root, child);
        } else {
            registry.retractNode(root);
            vm.recordLogs();
            registry.retractNode(root);
        }
        assertEq(vm.getRecordedLogs().length, 0);
        vm.stopPrank();
    }

    function testFuzzRejectsTwoNodeSupersessionCycle(bytes32 seed) public {
        (bytes32 root, bytes32 child) = _seedNodes(seed);

        vm.startPrank(REGISTRAR);
        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.InvalidSupersededBy.selector, root)
        );
        registry.supersedeNode(root, root);
        registry.supersedeNode(root, child);
        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.InvalidSupersededBy.selector, root)
        );
        registry.supersedeNode(child, root);
        vm.stopPrank();
    }

    function testFuzzRejectsThreeNodeSupersessionCycle(bytes32 seed) public {
        (bytes32 root, bytes32 child) = _seedNodes(seed);
        bytes32 treeUid = registry.getNode(root).treeUid;
        bytes32 third = _nonzeroUid(seed, 5);
        _registerNode(
            third, _nonzeroUid(seed, 6), treeUid, child, seed, _publisher(address(3), seed, 3)
        );

        vm.startPrank(REGISTRAR);
        registry.supersedeNode(root, child);
        registry.supersedeNode(child, third);
        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.InvalidSupersededBy.selector, root)
        );
        registry.supersedeNode(third, root);
        vm.stopPrank();
    }

    function testFuzzRejectsTerminalSuccessor(bytes32 seed) public {
        (bytes32 root, bytes32 child) = _seedNodes(seed);
        bytes32 treeUid = registry.getNode(root).treeUid;
        bytes32 third = _nonzeroUid(seed, 5);
        _registerNode(
            third, _nonzeroUid(seed, 6), treeUid, child, seed, _publisher(address(3), seed, 3)
        );

        vm.startPrank(REGISTRAR);
        registry.retractNode(child);
        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.InvalidSupersededBy.selector, child)
        );
        registry.supersedeNode(root, child);
        registry.supersedeNode(third, root);
        vm.expectRevert(
            abi.encodeWithSelector(TechtreeGraphRegistryV1.InvalidSupersededBy.selector, third)
        );
        registry.supersedeNode(root, third);
        vm.stopPrank();
    }

    function _seedNodes(bytes32 seed) internal returns (bytes32 root, bytes32 child) {
        bytes32 treeUid = _nonzeroUid(seed, 0);
        root = _nonzeroUid(seed, 1);
        child = _nonzeroUid(seed, 2);
        _registerTree(treeUid);
        _registerNode(
            root, _nonzeroUid(seed, 3), treeUid, bytes32(0), seed, _publisher(address(1), seed, 1)
        );
        _registerNode(
            child, _nonzeroUid(seed, 4), treeUid, root, seed, _publisher(address(2), seed, 2)
        );
    }

    function _registerTree(bytes32 treeUid) internal {
        vm.prank(REGISTRAR);
        registry.registerTree(treeUid);
    }

    function _registerNode(
        bytes32 nodeUid,
        bytes32 revisionUid,
        bytes32 treeUid,
        bytes32 parentNodeUid,
        bytes32 nodeKind,
        TechtreeGraphRegistryV1.RecordedPublisher memory publisher
    ) internal {
        vm.prank(REGISTRAR);
        registry.registerNode(nodeUid, revisionUid, treeUid, parentNodeUid, nodeKind, publisher);
    }

    function _registerEdge(
        bytes32 edgeUid,
        bytes32 root,
        bytes32 child,
        TechtreeGraphRegistryV1.EdgeKind kind
    ) internal {
        vm.prank(REGISTRAR);
        registry.registerEdge(edgeUid, root, child, kind);
    }

    function _publisher(address publisherRegistry, bytes32 agentId, uint256 tokenId)
        internal
        pure
        returns (TechtreeGraphRegistryV1.RecordedPublisher memory)
    {
        return TechtreeGraphRegistryV1.RecordedPublisher({
            registry: publisherRegistry, agentId: agentId, tokenId: tokenId
        });
    }

    function _nonzeroUid(bytes32 seed, uint256 index) internal pure returns (bytes32 uid) {
        uid = keccak256(abi.encode(seed, index));
        if (uid == bytes32(0)) return bytes32(uint256(index + 1));
    }

    function _add(uint256 left, uint256 right) internal pure returns (uint256 result) {
        unchecked {
            return left + right;
        }
    }
}
