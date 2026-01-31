;; ============================================================
;; Agent DAO Token Template
;; ============================================================
;; SIP-010 compliant token for agent DAOs.
;; Deploy with custom name/symbol for each DAO.
;;
;; Based on aibtcdev-daos token structure with:
;; - Fixed supply (1 billion)
;; - DAO-controlled minting for distributions
;; - Burn capability
;; ============================================================

;; ============================================================
;; Traits
;; ============================================================

(impl-trait 'SP3FBR2AGK5H9QBDH3EEN6DF8EK8JY7RX8QJ5SVTE.sip-010-trait-ft-standard.sip-010-trait)

;; ============================================================
;; Constants
;; ============================================================

;; Token metadata - CUSTOMIZE THESE PER DAO
(define-constant TOKEN_NAME "Agent DAO Token")
(define-constant TOKEN_SYMBOL "ADT")
(define-constant TOKEN_DECIMALS u8)
(define-constant TOKEN_URI (some u"https://aibtc.dev/tokens/agent-dao.json"))

;; Supply constants
(define-constant MAX_SUPPLY u1000000000000000000)  ;; 1 billion with 8 decimals
(define-constant INITIAL_SUPPLY u0)  ;; Minted during distribution

;; Allocation constants (basis points)
(define-constant FOUNDER_BP u5000)      ;; 50%
(define-constant PARTICIPANT_BP u3000)  ;; 30%
(define-constant TREASURY_BP u1500)     ;; 15%
(define-constant VERIFIER_BP u500)      ;; 5%

;; Errors
(define-constant ERR_UNAUTHORIZED (err u2001))
(define-constant ERR_INSUFFICIENT_BALANCE (err u2002))
(define-constant ERR_INVALID_AMOUNT (err u2003))
(define-constant ERR_ALREADY_DISTRIBUTED (err u2004))

;; ============================================================
;; Data Variables
;; ============================================================

(define-data-var token-owner principal tx-sender)
(define-data-var total-minted uint u0)
(define-data-var distribution-complete bool false)

;; ============================================================
;; Data Maps
;; ============================================================

(define-map token-balances principal uint)

;; ============================================================
;; SIP-010 Implementation
;; ============================================================

(define-fungible-token agent-dao-token MAX_SUPPLY)

;; Transfer tokens
(define-public (transfer
    (amount uint)
    (sender principal)
    (recipient principal)
    (memo (optional (buff 34))))
  (begin
    (asserts! (is-eq tx-sender sender) ERR_UNAUTHORIZED)
    (asserts! (> amount u0) ERR_INVALID_AMOUNT)
    (try! (ft-transfer? agent-dao-token amount sender recipient))
    (match memo to-print (print to-print) 0x)
    (ok true)
  )
)

;; Get token name
(define-read-only (get-name)
  (ok TOKEN_NAME)
)

;; Get token symbol
(define-read-only (get-symbol)
  (ok TOKEN_SYMBOL)
)

;; Get decimals
(define-read-only (get-decimals)
  (ok TOKEN_DECIMALS)
)

;; Get balance
(define-read-only (get-balance (account principal))
  (ok (ft-get-balance agent-dao-token account))
)

;; Get total supply
(define-read-only (get-total-supply)
  (ok (ft-get-supply agent-dao-token))
)

;; Get token URI
(define-read-only (get-token-uri)
  (ok TOKEN_URI)
)

;; ============================================================
;; Distribution Functions
;; ============================================================

;; Mint tokens to founder (50%)
(define-public (distribute-founder (founder principal))
  (let (
    (amount (/ (* MAX_SUPPLY FOUNDER_BP) u10000))
  )
    (asserts! (is-eq tx-sender (var-get token-owner)) ERR_UNAUTHORIZED)
    (asserts! (not (var-get distribution-complete)) ERR_ALREADY_DISTRIBUTED)
    (try! (ft-mint? agent-dao-token amount founder))
    (var-set total-minted (+ (var-get total-minted) amount))
    (ok amount)
  )
)

;; Mint tokens to participant (from 30% pool)
(define-public (distribute-participant
    (participant principal)
    (allocation-bp uint))  ;; Their share of the 30% pool
  (let (
    (participant-pool (/ (* MAX_SUPPLY PARTICIPANT_BP) u10000))
    (amount (/ (* participant-pool allocation-bp) u10000))
  )
    (asserts! (is-eq tx-sender (var-get token-owner)) ERR_UNAUTHORIZED)
    (asserts! (not (var-get distribution-complete)) ERR_ALREADY_DISTRIBUTED)
    (try! (ft-mint? agent-dao-token amount participant))
    (var-set total-minted (+ (var-get total-minted) amount))
    (ok amount)
  )
)

;; Mint tokens to treasury (15%)
(define-public (distribute-treasury (treasury principal))
  (let (
    (amount (/ (* MAX_SUPPLY TREASURY_BP) u10000))
  )
    (asserts! (is-eq tx-sender (var-get token-owner)) ERR_UNAUTHORIZED)
    (asserts! (not (var-get distribution-complete)) ERR_ALREADY_DISTRIBUTED)
    (try! (ft-mint? agent-dao-token amount treasury))
    (var-set total-minted (+ (var-get total-minted) amount))
    (ok amount)
  )
)

;; Mint tokens to verifier (5%)
(define-public (distribute-verifier (verifier principal))
  (let (
    (amount (/ (* MAX_SUPPLY VERIFIER_BP) u10000))
  )
    (asserts! (is-eq tx-sender (var-get token-owner)) ERR_UNAUTHORIZED)
    (asserts! (not (var-get distribution-complete)) ERR_ALREADY_DISTRIBUTED)
    (try! (ft-mint? agent-dao-token amount verifier))
    (var-set total-minted (+ (var-get total-minted) amount))
    (ok amount)
  )
)

;; Mark distribution as complete
(define-public (finalize-distribution)
  (begin
    (asserts! (is-eq tx-sender (var-get token-owner)) ERR_UNAUTHORIZED)
    (var-set distribution-complete true)
    (ok true)
  )
)

;; ============================================================
;; Owner Functions
;; ============================================================

;; Transfer ownership to DAO
(define-public (transfer-ownership (new-owner principal))
  (begin
    (asserts! (is-eq tx-sender (var-get token-owner)) ERR_UNAUTHORIZED)
    (var-set token-owner new-owner)
    (ok true)
  )
)

;; Mint additional tokens (DAO only, post-distribution for rewards)
(define-public (mint (amount uint) (recipient principal))
  (begin
    (asserts! (is-eq tx-sender (var-get token-owner)) ERR_UNAUTHORIZED)
    (asserts! (var-get distribution-complete) ERR_UNAUTHORIZED)
    (asserts! (<= (+ (ft-get-supply agent-dao-token) amount) MAX_SUPPLY) ERR_INVALID_AMOUNT)
    (ft-mint? agent-dao-token amount recipient)
  )
)

;; Burn tokens
(define-public (burn (amount uint) (owner principal))
  (begin
    (asserts! (is-eq tx-sender owner) ERR_UNAUTHORIZED)
    (ft-burn? agent-dao-token amount owner)
  )
)

;; ============================================================
;; Read-Only Helpers
;; ============================================================

(define-read-only (get-owner)
  (var-get token-owner)
)

(define-read-only (get-total-minted)
  (var-get total-minted)
)

(define-read-only (is-distribution-complete)
  (var-get distribution-complete)
)

(define-read-only (get-founder-amount)
  (/ (* MAX_SUPPLY FOUNDER_BP) u10000)
)

(define-read-only (get-participant-pool)
  (/ (* MAX_SUPPLY PARTICIPANT_BP) u10000)
)

(define-read-only (get-treasury-amount)
  (/ (* MAX_SUPPLY TREASURY_BP) u10000)
)

(define-read-only (get-verifier-amount)
  (/ (* MAX_SUPPLY VERIFIER_BP) u10000)
)
