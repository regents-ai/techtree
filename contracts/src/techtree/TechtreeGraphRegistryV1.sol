// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

/// @title TechtreeGraphRegistryV1
/// @notice Stores structural assertions recorded by the Regent registrar for Techtree.
/// @dev Records are not proofs of content, authorship, or correctness. This contract stores no
///      content, content commitments, CIDs, scores, or coordinates.
contract TechtreeGraphRegistryV1 {
    /// @notice Maximum number of records accepted by either batch registration function.
    uint256 public constant MAX_BATCH_SIZE = 100;

    enum TreeStatus {
        ACTIVE,
        RETIRED
    }

    enum NodeStatus {
        PUBLISHED,
        SUPERSEDED,
        RETRACTED
    }

    enum EdgeKind {
        DERIVED_FROM,
        SUPPORTS,
        CONTRADICTS,
        REPRODUCES,
        FAILS_TO_REPRODUCE,
        SUPERSEDES
    }

    enum EdgeStatus {
        ACTIVE,
        RETRACTED
    }

    struct RecordedPublisher {
        address registry;
        bytes32 agentId;
        uint256 tokenId;
    }

    struct TreeRecord {
        bytes32 treeUid;
        TreeStatus status;
    }

    struct NodeRecord {
        bytes32 nodeUid;
        bytes32 revisionUid;
        bytes32 treeUid;
        bytes32 parentNodeUid;
        bytes32 nodeKind;
        RecordedPublisher recordedPublisher;
        NodeStatus status;
        bytes32 supersededBy;
    }

    struct EdgeRecord {
        bytes32 edgeUid;
        bytes32 fromNodeUid;
        bytes32 toNodeUid;
        EdgeKind kind;
        EdgeStatus status;
    }

    struct NodeInput {
        bytes32 nodeUid;
        bytes32 revisionUid;
        bytes32 treeUid;
        bytes32 parentNodeUid;
        bytes32 nodeKind;
        RecordedPublisher recordedPublisher;
    }

    struct EdgeInput {
        bytes32 edgeUid;
        bytes32 fromNodeUid;
        bytes32 toNodeUid;
        EdgeKind kind;
    }

    error Unauthorized(address caller);
    error ZeroAddress();
    error ZeroUid();
    error RecordNotFound(bytes32 uid);
    error RecordConflict(bytes32 uid);
    error InvalidStatusTransition(uint8 currentStatus, uint8 requestedStatus);
    error InvalidSupersededBy(bytes32 supersededBy);
    error InvalidBatchLength(uint256 length);
    error RegistrarUnchanged();
    error OwnerUnchanged();
    error RoleCollision(address account);
    error RevisionUpdateNotAllowed(bytes32 nodeUid, NodeStatus status);

    event OwnershipTransferStarted(address indexed previousOwner, address indexed pendingOwner);
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);
    event RegistrarUpdated(address indexed previousRegistrar, address indexed newRegistrar);
    event TreeRegistered(bytes32 indexed treeUid, TreeStatus status);
    event TreeStatusUpdated(bytes32 indexed treeUid, TreeStatus previousStatus, TreeStatus status);
    event NodeRegistered(
        bytes32 indexed nodeUid,
        bytes32 revisionUid,
        bytes32 indexed treeUid,
        bytes32 indexed parentNodeUid,
        bytes32 nodeKind,
        address publisherRegistry,
        bytes32 publisherAgentId,
        uint256 publisherTokenId,
        NodeStatus status,
        bytes32 supersededBy
    );
    event NodeStatusUpdated(
        bytes32 indexed nodeUid,
        bytes32 revisionUid,
        bytes32 indexed treeUid,
        bytes32 indexed parentNodeUid,
        bytes32 nodeKind,
        address publisherRegistry,
        bytes32 publisherAgentId,
        uint256 publisherTokenId,
        NodeStatus previousStatus,
        NodeStatus status,
        bytes32 supersededBy
    );
    event NodeRevisionRegistered(
        bytes32 indexed nodeUid, bytes32 previousRevisionUid, bytes32 newRevisionUid
    );
    event EdgeRegistered(
        bytes32 indexed edgeUid,
        bytes32 indexed fromNodeUid,
        bytes32 indexed toNodeUid,
        EdgeKind kind,
        EdgeStatus status
    );
    event EdgeStatusUpdated(
        bytes32 indexed edgeUid,
        bytes32 indexed fromNodeUid,
        bytes32 indexed toNodeUid,
        EdgeKind kind,
        EdgeStatus previousStatus,
        EdgeStatus status
    );

    /// @notice The account authorized to manage ownership and rotate the registrar.
    address public owner;
    /// @notice The account currently nominated to accept ownership.
    address public pendingOwner;
    /// @notice The sole account authorized to write graph records.
    address public registrar;

    mapping(bytes32 treeUid => TreeRecord record) private _trees;
    mapping(bytes32 nodeUid => NodeRecord record) private _nodes;
    mapping(bytes32 edgeUid => EdgeRecord record) private _edges;

    modifier onlyOwner() {
        _checkOwner();
        _;
    }

    modifier onlyRegistrar() {
        _checkRegistrar();
        _;
    }

    /// @notice Creates the registry with its protected owner and dedicated registrar.
    /// @param initialOwner The protected administrative owner.
    /// @param initialRegistrar The sole account authorized to record graph assertions.
    constructor(address initialOwner, address initialRegistrar) {
        if (initialOwner == address(0) || initialRegistrar == address(0)) revert ZeroAddress();
        if (initialOwner == initialRegistrar) revert RoleCollision(initialOwner);
        owner = initialOwner;
        registrar = initialRegistrar;
        emit OwnershipTransferred(address(0), initialOwner);
        emit RegistrarUpdated(address(0), initialRegistrar);
    }

    /// @notice Starts a two-step transfer of ownership.
    /// @param newOwner The account that must accept ownership.
    function transferOwnership(address newOwner) external onlyOwner {
        if (newOwner == address(0)) revert ZeroAddress();
        if (newOwner == registrar) revert RoleCollision(newOwner);
        if (newOwner == owner || newOwner == pendingOwner) revert OwnerUnchanged();
        pendingOwner = newOwner;
        emit OwnershipTransferStarted(owner, newOwner);
    }

    /// @notice Accepts ownership as the pending owner.
    function acceptOwnership() external {
        if (msg.sender != pendingOwner) revert Unauthorized(msg.sender);
        address previousOwner = owner;
        owner = msg.sender;
        pendingOwner = address(0);
        emit OwnershipTransferred(previousOwner, msg.sender);
    }

    /// @notice Rotates the sole registrar account.
    /// @param newRegistrar The new dedicated graph registrar.
    function setRegistrar(address newRegistrar) external onlyOwner {
        if (newRegistrar == address(0)) revert ZeroAddress();
        if (newRegistrar == owner || newRegistrar == pendingOwner) {
            revert RoleCollision(newRegistrar);
        }
        if (newRegistrar == registrar) revert RegistrarUnchanged();
        address previousRegistrar = registrar;
        registrar = newRegistrar;
        emit RegistrarUpdated(previousRegistrar, newRegistrar);
    }

    /// @notice Registers a Tree UID, or silently succeeds if it is already registered.
    /// @param treeUid The opaque, caller-supplied Tree UID.
    function registerTree(bytes32 treeUid) external onlyRegistrar {
        if (treeUid == bytes32(0)) revert ZeroUid();
        if (_trees[treeUid].treeUid != bytes32(0)) return;

        _trees[treeUid] = TreeRecord({treeUid: treeUid, status: TreeStatus.ACTIVE});
        emit TreeRegistered(treeUid, TreeStatus.ACTIVE);
    }

    /// @notice Retires an active Tree; retirement is terminal.
    /// @param treeUid The registered Tree UID.
    function retireTree(bytes32 treeUid) external onlyRegistrar {
        if (_trees[treeUid].treeUid == bytes32(0)) revert RecordNotFound(treeUid);
        TreeRecord storage record = _trees[treeUid];
        if (record.status == TreeStatus.RETIRED) return;
        if (record.status != TreeStatus.ACTIVE) {
            revert InvalidStatusTransition(uint8(record.status), uint8(TreeStatus.RETIRED));
        }
        record.status = TreeStatus.RETIRED;
        emit TreeStatusUpdated(treeUid, TreeStatus.ACTIVE, TreeStatus.RETIRED);
    }

    /// @notice Registers one Node structural assertion.
    /// @param nodeUid The opaque, caller-supplied Node UID.
    /// @param revisionUid The opaque, caller-supplied current revision UID.
    /// @param treeUid The registered Tree containing the Node.
    /// @param parentNodeUid The registered parent Node, or zero for a root Node.
    /// @param nodeKind An opaque structural Node kind.
    /// @param recordedPublisher The publisher identity tuple mirrored by the registrar.
    function registerNode(
        bytes32 nodeUid,
        bytes32 revisionUid,
        bytes32 treeUid,
        bytes32 parentNodeUid,
        bytes32 nodeKind,
        RecordedPublisher calldata recordedPublisher
    ) external onlyRegistrar {
        _registerNode(
            NodeInput({
                nodeUid: nodeUid,
                revisionUid: revisionUid,
                treeUid: treeUid,
                parentNodeUid: parentNodeUid,
                nodeKind: nodeKind,
                recordedPublisher: recordedPublisher
            })
        );
    }

    /// @notice Registers up to 100 Node structural assertions atomically.
    /// @param inputs The Node assertions, ordered so any in-batch parent appears first.
    function registerNodes(NodeInput[] calldata inputs) external onlyRegistrar {
        uint256 length = inputs.length;
        if (length == 0 || length > MAX_BATCH_SIZE) revert InvalidBatchLength(length);
        for (uint256 i; i < length; ++i) {
            _registerNode(inputs[i]);
        }
    }

    /// @notice Registers a new current revision UID for a published Node.
    /// @param nodeUid The published Node receiving the revision.
    /// @param newRevisionUid The new opaque revision UID.
    function registerNodeRevision(bytes32 nodeUid, bytes32 newRevisionUid) external onlyRegistrar {
        if (nodeUid == bytes32(0) || newRevisionUid == bytes32(0)) revert ZeroUid();
        if (_nodes[nodeUid].nodeUid == bytes32(0)) revert RecordNotFound(nodeUid);

        NodeRecord storage record = _nodes[nodeUid];
        if (record.status != NodeStatus.PUBLISHED) {
            revert RevisionUpdateNotAllowed(nodeUid, record.status);
        }
        bytes32 previousRevisionUid = record.revisionUid;
        if (newRevisionUid == previousRevisionUid) return;

        record.revisionUid = newRevisionUid;
        emit NodeRevisionRegistered(nodeUid, previousRevisionUid, newRevisionUid);
    }

    /// @notice Supersedes a published Node with another registered Node.
    /// @param nodeUid The published Node being superseded.
    /// @param supersededBy The registered replacement Node UID.
    function supersedeNode(bytes32 nodeUid, bytes32 supersededBy) external onlyRegistrar {
        if (_nodes[nodeUid].nodeUid == bytes32(0)) revert RecordNotFound(nodeUid);

        NodeRecord storage record = _nodes[nodeUid];
        if (record.status == NodeStatus.SUPERSEDED) {
            if (record.supersededBy == supersededBy) return;
            revert RecordConflict(nodeUid);
        }
        if (record.status != NodeStatus.PUBLISHED) {
            revert InvalidStatusTransition(uint8(record.status), uint8(NodeStatus.SUPERSEDED));
        }
        if (
            supersededBy == bytes32(0) || supersededBy == nodeUid
                || _nodes[supersededBy].nodeUid == bytes32(0)
                || _nodes[supersededBy].status != NodeStatus.PUBLISHED
        ) revert InvalidSupersededBy(supersededBy);

        NodeStatus previousStatus = record.status;
        record.status = NodeStatus.SUPERSEDED;
        record.supersededBy = supersededBy;
        _emitNodeStatusUpdated(record, previousStatus);
    }

    /// @notice Retracts a published Node; retraction is terminal.
    /// @param nodeUid The published Node UID.
    function retractNode(bytes32 nodeUid) external onlyRegistrar {
        if (_nodes[nodeUid].nodeUid == bytes32(0)) revert RecordNotFound(nodeUid);
        NodeRecord storage record = _nodes[nodeUid];
        if (record.status == NodeStatus.RETRACTED) return;
        if (record.status != NodeStatus.PUBLISHED) {
            revert InvalidStatusTransition(uint8(record.status), uint8(NodeStatus.RETRACTED));
        }
        NodeStatus previousStatus = record.status;
        record.status = NodeStatus.RETRACTED;
        _emitNodeStatusUpdated(record, previousStatus);
    }

    /// @notice Registers one typed semantic Edge assertion.
    /// @param edgeUid The opaque, caller-supplied Edge UID.
    /// @param fromNodeUid The registered source Node UID.
    /// @param toNodeUid The registered target Node UID.
    /// @param kind One of the six v1 semantic Edge kinds.
    function registerEdge(bytes32 edgeUid, bytes32 fromNodeUid, bytes32 toNodeUid, EdgeKind kind)
        external
        onlyRegistrar
    {
        _registerEdge(
            EdgeInput({
                edgeUid: edgeUid, fromNodeUid: fromNodeUid, toNodeUid: toNodeUid, kind: kind
            })
        );
    }

    /// @notice Registers up to 100 typed semantic Edge assertions atomically.
    /// @param inputs The Edge assertions; both endpoint Nodes must already exist.
    function registerEdges(EdgeInput[] calldata inputs) external onlyRegistrar {
        uint256 length = inputs.length;
        if (length == 0 || length > MAX_BATCH_SIZE) revert InvalidBatchLength(length);
        for (uint256 i; i < length; ++i) {
            _registerEdge(inputs[i]);
        }
    }

    /// @notice Retracts an active Edge; retraction is terminal.
    /// @param edgeUid The registered Edge UID.
    function retractEdge(bytes32 edgeUid) external onlyRegistrar {
        if (_edges[edgeUid].edgeUid == bytes32(0)) revert RecordNotFound(edgeUid);
        EdgeRecord storage record = _edges[edgeUid];
        if (record.status == EdgeStatus.RETRACTED) return;
        if (record.status != EdgeStatus.ACTIVE) {
            revert InvalidStatusTransition(uint8(record.status), uint8(EdgeStatus.RETRACTED));
        }
        EdgeStatus previousStatus = record.status;
        record.status = EdgeStatus.RETRACTED;
        emit EdgeStatusUpdated(
            record.edgeUid,
            record.fromNodeUid,
            record.toNodeUid,
            record.kind,
            previousStatus,
            record.status
        );
    }

    /// @notice Returns a registered Tree record.
    /// @param treeUid The Tree UID to read.
    /// @return record The complete Tree record.
    function getTree(bytes32 treeUid) external view returns (TreeRecord memory record) {
        if (_trees[treeUid].treeUid == bytes32(0)) revert RecordNotFound(treeUid);
        return _trees[treeUid];
    }

    /// @notice Returns a registered Node record.
    /// @param nodeUid The Node UID to read.
    /// @return record The complete Node record.
    function getNode(bytes32 nodeUid) external view returns (NodeRecord memory record) {
        if (_nodes[nodeUid].nodeUid == bytes32(0)) revert RecordNotFound(nodeUid);
        return _nodes[nodeUid];
    }

    /// @notice Returns a registered Edge record.
    /// @param edgeUid The Edge UID to read.
    /// @return record The complete Edge record.
    function getEdge(bytes32 edgeUid) external view returns (EdgeRecord memory record) {
        if (_edges[edgeUid].edgeUid == bytes32(0)) revert RecordNotFound(edgeUid);
        return _edges[edgeUid];
    }

    function _registerNode(NodeInput memory input) private {
        if (
            input.nodeUid == bytes32(0) || input.revisionUid == bytes32(0)
                || input.treeUid == bytes32(0)
        ) revert ZeroUid();
        if (_trees[input.treeUid].treeUid == bytes32(0)) revert RecordNotFound(input.treeUid);
        if (input.parentNodeUid != bytes32(0) && _nodes[input.parentNodeUid].nodeUid == bytes32(0))
        {
            revert RecordNotFound(input.parentNodeUid);
        }

        if (_nodes[input.nodeUid].nodeUid != bytes32(0)) {
            if (!_sameNode(_nodes[input.nodeUid], input)) revert RecordConflict(input.nodeUid);
            return;
        }

        NodeRecord storage record = _nodes[input.nodeUid];
        record.nodeUid = input.nodeUid;
        record.revisionUid = input.revisionUid;
        record.treeUid = input.treeUid;
        record.parentNodeUid = input.parentNodeUid;
        record.nodeKind = input.nodeKind;
        record.recordedPublisher = input.recordedPublisher;
        record.status = NodeStatus.PUBLISHED;
        _emitNodeRegistered(record);
    }

    function _registerEdge(EdgeInput memory input) private {
        if (
            input.edgeUid == bytes32(0) || input.fromNodeUid == bytes32(0)
                || input.toNodeUid == bytes32(0)
        ) revert ZeroUid();
        if (_nodes[input.fromNodeUid].nodeUid == bytes32(0)) {
            revert RecordNotFound(input.fromNodeUid);
        }
        if (_nodes[input.toNodeUid].nodeUid == bytes32(0)) revert RecordNotFound(input.toNodeUid);

        if (_edges[input.edgeUid].edgeUid != bytes32(0)) {
            if (!_sameEdge(_edges[input.edgeUid], input)) revert RecordConflict(input.edgeUid);
            return;
        }

        _edges[input.edgeUid] = EdgeRecord({
            edgeUid: input.edgeUid,
            fromNodeUid: input.fromNodeUid,
            toNodeUid: input.toNodeUid,
            kind: input.kind,
            status: EdgeStatus.ACTIVE
        });
        emit EdgeRegistered(
            input.edgeUid, input.fromNodeUid, input.toNodeUid, input.kind, EdgeStatus.ACTIVE
        );
    }

    function _sameNode(NodeRecord storage record, NodeInput memory input)
        private
        view
        returns (bool)
    {
        return record.revisionUid == input.revisionUid && record.treeUid == input.treeUid
            && record.parentNodeUid == input.parentNodeUid && record.nodeKind == input.nodeKind
            && record.recordedPublisher.registry == input.recordedPublisher.registry
            && record.recordedPublisher.agentId == input.recordedPublisher.agentId
            && record.recordedPublisher.tokenId == input.recordedPublisher.tokenId;
    }

    function _sameEdge(EdgeRecord storage record, EdgeInput memory input)
        private
        view
        returns (bool)
    {
        return record.fromNodeUid == input.fromNodeUid && record.toNodeUid == input.toNodeUid
            && record.kind == input.kind;
    }

    function _emitNodeRegistered(NodeRecord storage record) private {
        emit NodeRegistered(
            record.nodeUid,
            record.revisionUid,
            record.treeUid,
            record.parentNodeUid,
            record.nodeKind,
            record.recordedPublisher.registry,
            record.recordedPublisher.agentId,
            record.recordedPublisher.tokenId,
            record.status,
            record.supersededBy
        );
    }

    function _emitNodeStatusUpdated(NodeRecord storage record, NodeStatus previousStatus) private {
        emit NodeStatusUpdated(
            record.nodeUid,
            record.revisionUid,
            record.treeUid,
            record.parentNodeUid,
            record.nodeKind,
            record.recordedPublisher.registry,
            record.recordedPublisher.agentId,
            record.recordedPublisher.tokenId,
            previousStatus,
            record.status,
            record.supersededBy
        );
    }

    function _checkOwner() private view {
        if (msg.sender != owner) revert Unauthorized(msg.sender);
    }

    function _checkRegistrar() private view {
        if (msg.sender != registrar) revert Unauthorized(msg.sender);
    }
}
