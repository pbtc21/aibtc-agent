;; ============================================================
;; Agent DAO Participant Whitelist
;; ============================================================
;; Manages whitelisted addresses for agent DAOs created from
;; Moltbook discussions. Integrates with aibtcdev-daos contracts.
;;
;; Flow:
;; 1. Proposer creates DAO proposal linked to Moltbook post
;; 2. Participants added to whitelist (verified via MCP)
;; 3. When threshold met, DAO can be deployed
;; 4. Whitelist used for token distribution
;; ============================================================

;; ============================================================
;; Constants
;; ============================================================

(define-constant CONTRACT_OWNER tx-sender)

;; Errors
(define-constant ERR_UNAUTHORIZED (err u1001))
(define-constant ERR_ALREADY_EXISTS (err u1002))
(define-constant ERR_NOT_FOUND (err u1003))
(define-constant ERR_INVALID_ADDRESS (err u1004))
(define-constant ERR_THRESHOLD_NOT_MET (err u1005))
(define-constant ERR_ALREADY_DEPLOYED (err u1006))
(define-constant ERR_INVALID_ALLOCATION (err u1007))
(define-constant ERR_MAX_PARTICIPANTS (err u1008))

;; Allocation constants (basis points, 10000 = 100%)
(define-constant FOUNDER_ALLOCATION u5000)      ;; 50% to proposer
(define-constant PARTICIPANT_ALLOCATION u3000)  ;; 30% split among participants
(define-constant TREASURY_ALLOCATION u1500)     ;; 15% to DAO treasury
(define-constant VERIFIER_ALLOCATION u500)      ;; 5% to verifier/appleseed

;; Thresholds
(define-constant MIN_PARTICIPANTS u10)
(define-constant MAX_PARTICIPANTS u50)

;; ============================================================
;; Data Variables
;; ============================================================

(define-data-var dao-counter uint u0)

;; ============================================================
;; Data Maps
;; ============================================================

;; DAO proposals from Moltbook discussions
(define-map dao-proposals
  { dao-id: uint }
  {
    moltbook-post-id: (string-ascii 64),
    proposer: principal,
    name: (string-ascii 32),
    description: (string-utf8 256),
    participant-count: uint,
    status: (string-ascii 20),  ;; "gathering", "threshold_met", "deployed"
    token-address: (optional principal),
    treasury-address: (optional principal),
    created-at: uint,
    deployed-at: (optional uint)
  }
)

;; Whitelisted participants per DAO
(define-map whitelisted-participants
  { dao-id: uint, participant: principal }
  {
    agent-name: (string-ascii 32),
    mcp-verified: bool,
    allocation-bp: uint,  ;; basis points of participant pool
    added-at: uint,
    claimed: bool
  }
)

;; Participant list per DAO (for enumeration)
(define-map dao-participant-list
  { dao-id: uint, index: uint }
  { participant: principal }
)

;; Reverse lookup: find DAOs a participant is in
(define-map participant-daos
  { participant: principal, dao-id: uint }
  { joined: bool }
)

;; ============================================================
;; Read-Only Functions
;; ============================================================

;; Get DAO proposal details
(define-read-only (get-dao-proposal (dao-id uint))
  (map-get? dao-proposals { dao-id: dao-id })
)

;; Check if address is whitelisted for a DAO
(define-read-only (is-whitelisted (dao-id uint) (address principal))
  (is-some (map-get? whitelisted-participants { dao-id: dao-id, participant: address }))
)

;; Get participant details
(define-read-only (get-participant (dao-id uint) (address principal))
  (map-get? whitelisted-participants { dao-id: dao-id, participant: address })
)

;; Get participant allocation in basis points
(define-read-only (get-allocation-bp (dao-id uint) (address principal))
  (default-to u0
    (get allocation-bp
      (map-get? whitelisted-participants { dao-id: dao-id, participant: address })))
)

;; Calculate actual token allocation from basis points
;; total-supply: total token supply
;; Returns: tokens for this participant
(define-read-only (calculate-token-allocation
    (dao-id uint)
    (address principal)
    (total-supply uint))
  (let (
    (participant-bp (get-allocation-bp dao-id address))
    (participant-pool (/ (* total-supply PARTICIPANT_ALLOCATION) u10000))
  )
    (/ (* participant-pool participant-bp) u10000)
  )
)

;; Get founder allocation
(define-read-only (get-founder-allocation (total-supply uint))
  (/ (* total-supply FOUNDER_ALLOCATION) u10000)
)

;; Get treasury allocation
(define-read-only (get-treasury-allocation (total-supply uint))
  (/ (* total-supply TREASURY_ALLOCATION) u10000)
)

;; Get verifier allocation
(define-read-only (get-verifier-allocation (total-supply uint))
  (/ (* total-supply VERIFIER_ALLOCATION) u10000)
)

;; Check if threshold met for DAO creation
(define-read-only (threshold-met (dao-id uint))
  (match (get-dao-proposal dao-id)
    proposal (>= (get participant-count proposal) MIN_PARTICIPANTS)
    false
  )
)

;; Get current DAO counter
(define-read-only (get-dao-count)
  (var-get dao-counter)
)

;; ============================================================
;; Public Functions
;; ============================================================

;; Create a new DAO proposal from Moltbook discussion
(define-public (create-dao-proposal
    (moltbook-post-id (string-ascii 64))
    (name (string-ascii 32))
    (description (string-utf8 256)))
  (let (
    (new-id (+ (var-get dao-counter) u1))
  )
    ;; Create the proposal
    (map-set dao-proposals
      { dao-id: new-id }
      {
        moltbook-post-id: moltbook-post-id,
        proposer: tx-sender,
        name: name,
        description: description,
        participant-count: u1,  ;; Proposer is first participant
        status: "gathering",
        token-address: none,
        treasury-address: none,
        created-at: burn-block-height,
        deployed-at: none
      }
    )

    ;; Add proposer as first participant with verified status
    (map-set whitelisted-participants
      { dao-id: new-id, participant: tx-sender }
      {
        agent-name: name,
        mcp-verified: true,  ;; Proposer assumed verified
        allocation-bp: u10000,  ;; 100% of participant pool initially
        added-at: burn-block-height,
        claimed: false
      }
    )

    ;; Add to participant list
    (map-set dao-participant-list
      { dao-id: new-id, index: u0 }
      { participant: tx-sender }
    )

    ;; Track participant's DAO membership
    (map-set participant-daos
      { participant: tx-sender, dao-id: new-id }
      { joined: true }
    )

    ;; Increment counter
    (var-set dao-counter new-id)

    (ok new-id)
  )
)

;; Add participant to whitelist (proposer or contract owner only)
(define-public (add-participant
    (dao-id uint)
    (participant principal)
    (agent-name (string-ascii 32))
    (mcp-verified bool))
  (let (
    (proposal (unwrap! (get-dao-proposal dao-id) ERR_NOT_FOUND))
    (current-count (get participant-count proposal))
  )
    ;; Authorization: only proposer or contract owner
    (asserts! (or
      (is-eq tx-sender (get proposer proposal))
      (is-eq tx-sender CONTRACT_OWNER))
      ERR_UNAUTHORIZED
    )

    ;; Check not already deployed
    (asserts! (is-eq (get status proposal) "gathering") ERR_ALREADY_DEPLOYED)

    ;; Check max participants
    (asserts! (< current-count MAX_PARTICIPANTS) ERR_MAX_PARTICIPANTS)

    ;; Check not already whitelisted
    (asserts! (not (is-whitelisted dao-id participant)) ERR_ALREADY_EXISTS)

    ;; Add to whitelist
    (map-set whitelisted-participants
      { dao-id: dao-id, participant: participant }
      {
        agent-name: agent-name,
        mcp-verified: mcp-verified,
        allocation-bp: u0,  ;; Will be calculated when finalized
        added-at: burn-block-height,
        claimed: false
      }
    )

    ;; Add to participant list
    (map-set dao-participant-list
      { dao-id: dao-id, index: current-count }
      { participant: participant }
    )

    ;; Track membership
    (map-set participant-daos
      { participant: participant, dao-id: dao-id }
      { joined: true }
    )

    ;; Update participant count
    (map-set dao-proposals
      { dao-id: dao-id }
      (merge proposal { participant-count: (+ current-count u1) })
    )

    ;; Check if threshold met and update status
    (if (>= (+ current-count u1) MIN_PARTICIPANTS)
      (map-set dao-proposals
        { dao-id: dao-id }
        (merge proposal {
          participant-count: (+ current-count u1),
          status: "threshold_met"
        })
      )
      true
    )

    (ok (+ current-count u1))
  )
)

;; Finalize allocations (calculate equal split among verified participants)
;; Called before DAO deployment
(define-public (finalize-allocations (dao-id uint))
  (let (
    (proposal (unwrap! (get-dao-proposal dao-id) ERR_NOT_FOUND))
    (count (get participant-count proposal))
  )
    ;; Authorization
    (asserts! (or
      (is-eq tx-sender (get proposer proposal))
      (is-eq tx-sender CONTRACT_OWNER))
      ERR_UNAUTHORIZED
    )

    ;; Must have met threshold
    (asserts! (>= count MIN_PARTICIPANTS) ERR_THRESHOLD_NOT_MET)

    ;; Calculate equal allocation per participant
    ;; Each gets 10000 / count basis points of the participant pool
    (let (
      (allocation-per (/ u10000 count))
    )
      ;; Note: In production, would iterate and update all participants
      ;; This is a simplified version - actual iteration requires helper
      (ok allocation-per)
    )
  )
)

;; Mark DAO as deployed (called after contract deployment)
(define-public (mark-deployed
    (dao-id uint)
    (token-address principal)
    (treasury-address principal))
  (let (
    (proposal (unwrap! (get-dao-proposal dao-id) ERR_NOT_FOUND))
  )
    ;; Authorization
    (asserts! (or
      (is-eq tx-sender (get proposer proposal))
      (is-eq tx-sender CONTRACT_OWNER))
      ERR_UNAUTHORIZED
    )

    ;; Must have met threshold
    (asserts! (>= (get participant-count proposal) MIN_PARTICIPANTS) ERR_THRESHOLD_NOT_MET)

    ;; Update proposal
    (map-set dao-proposals
      { dao-id: dao-id }
      (merge proposal {
        status: "deployed",
        token-address: (some token-address),
        treasury-address: (some treasury-address),
        deployed-at: (some burn-block-height)
      })
    )

    (ok true)
  )
)

;; Mark participant as having claimed tokens
(define-public (mark-claimed (dao-id uint) (participant principal))
  (let (
    (entry (unwrap! (get-participant dao-id participant) ERR_NOT_FOUND))
  )
    ;; Only the participant or contract owner can mark claimed
    (asserts! (or
      (is-eq tx-sender participant)
      (is-eq tx-sender CONTRACT_OWNER))
      ERR_UNAUTHORIZED
    )

    (map-set whitelisted-participants
      { dao-id: dao-id, participant: participant }
      (merge entry { claimed: true })
    )

    (ok true)
  )
)
