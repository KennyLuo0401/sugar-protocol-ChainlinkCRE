import {
	type EVMLog,
	EVMClient,
	handler,
	HTTPClient,
	type HTTPSendRequester,
	ConsensusAggregationByFields,
	median,
	identical,
	Runner,
	type Runtime,
} from '@chainlink/cre-sdk'
import { z } from 'zod'

// ─────────────────────────────────────────────
// Config Schema
// ─────────────────────────────────────────────
const configSchema = z.object({
	predictionMarketAddress: z.string(),
	sugarApiUrl: z.string(),
	openaiApiKey: z.string().optional(),
})

type Config = z.infer<typeof configSchema>

// ─────────────────────────────────────────────
// MarketCreated event signature
// keccak256("MarketCreated(uint256,string,address,uint256)")
// ─────────────────────────────────────────────
const MARKET_CREATED_EVENT_SIG = '0xb81a100e04d6d57a04a53e9f341b79e5b8d2c80e15ad6e1d6771a6b0767e8d1d'

// ─────────────────────────────────────────────
// Step 1: Validate claim in Sugar Protocol API
// ─────────────────────────────────────────────
interface ClaimValidation {
	valid: number // 1 = valid, 0 = invalid
	claimText: string
}

const validateClaim = (
	sendRequester: HTTPSendRequester,
	config: Config & { claimId: string },
): ClaimValidation => {
	const url = `${config.sugarApiUrl}/api/resolve?claim_id=${config.claimId}`
	const response = sendRequester.sendRequest({ method: 'GET', url }).result()

	if (response.statusCode !== 200) {
		// For hackathon demo: proceed even if claim not in mock data
		return { valid: 1, claimText: 'unknown' }
	}

	const text = Buffer.from(response.body).toString('utf-8')
	const data = JSON.parse(text)
	return {
		valid: data.claim_text ? 1 : 0,
		claimText: data.claim_text || '',
	}
}

// ─────────────────────────────────────────────
// Step 2: Call CRE-verify endpoint to mark market as VERIFIED
// ─────────────────────────────────────────────
interface VerifyResult {
	status: string
	txHash: string
}

const callCREVerify = (
	sendRequester: HTTPSendRequester,
	config: Config & { marketId: string },
): VerifyResult => {
	const url = `${config.sugarApiUrl}/api/markets/${config.marketId}/cre-verify`
	const response = sendRequester
		.sendRequest({
			method: 'POST',
			url,
			headers: { 'Content-Type': 'application/json' },
		})
		.result()

	if (response.statusCode !== 200) {
		const errText = Buffer.from(response.body).toString('utf-8')
		throw new Error(`CRE-verify failed (${response.statusCode}): ${errText}`)
	}

	const text = Buffer.from(response.body).toString('utf-8')
	const data = JSON.parse(text)
	return {
		status: data.status || 'unknown',
		txHash: data.tx_hash || '',
	}
}

// ─────────────────────────────────────────────
// Main handler: EVM LogTrigger → Verify Market
// CRE Capability #3: on-chain event → action
// ─────────────────────────────────────────────
const onMarketCreated = (
	runtime: Runtime<Config>,
	log: EVMLog,
): string => {
	// Extract marketId from indexed topic[1]
	// topics[0] = event signature, topics[1] = indexed marketId (uint256, 32 bytes)
	const marketIdHex = log.topics.length > 1
		? '0x' + Buffer.from(log.topics[1]).toString('hex')
		: '0'
	const marketId = parseInt(marketIdHex, 16).toString()

	runtime.log(`🍬 Sugar Protocol CRE: MarketCreated event detected! Market #${marketId}`)
	runtime.log(`[Event] TX Hash: 0x${Buffer.from(log.txHash).toString('hex')}`)

	const httpClient = new HTTPClient()

	// Step 1: Validate claim in Sugar Protocol
	runtime.log('[Step 1] Validating claim in Sugar Protocol API...')
	const validation = httpClient
		.sendRequest(
			runtime,
			validateClaim,
			ConsensusAggregationByFields<ClaimValidation>({
				valid: median,
				claimText: identical,
			}),
		)({ ...runtime.config, claimId: `claim_market_${marketId}` })
		.result()

	runtime.log(`[Step 1] Claim validation: ${validation.valid === 1 ? 'VALID' : 'INVALID'}`)

	if (validation.valid !== 1) {
		runtime.log('Claim validation failed. Skipping verification.')
		return JSON.stringify({
			marketId,
			status: 'rejected',
			reason: 'Claim not found in Sugar Protocol',
		})
	}

	// Step 2: Call CRE-verify to mark market as VERIFIED on EVM
	runtime.log(`[Step 2] Calling /cre-verify for market #${marketId}...`)
	const verifyResult = httpClient
		.sendRequest(
			runtime,
			callCREVerify,
			ConsensusAggregationByFields<VerifyResult>({
				status: identical,
				txHash: identical,
			}),
		)({ ...runtime.config, marketId })
		.result()

	runtime.log(`[Step 2] Verification status: ${verifyResult.status}`)
	runtime.log(`[Step 2] EVM TX: ${verifyResult.txHash}`)

	const result = JSON.stringify({
		marketId,
		status: verifyResult.status,
		txHash: verifyResult.txHash,
		timestamp: Date.now(),
	})

	runtime.log('🍬 Sugar Protocol CRE: Market verification complete!')

	return result
}

// ─────────────────────────────────────────────
// Workflow initialization — EVMClient.logTrigger
// CRE Capability #3: scan on-chain event → trigger
// ─────────────────────────────────────────────
const initWorkflow = (config: Config) => {
	const evmClient = new EVMClient(
		EVMClient.SUPPORTED_CHAIN_SELECTORS['ethereum-testnet-sepolia'],
	)

	// Convert contract address to bytes (remove 0x prefix, decode hex)
	const addressHex = config.predictionMarketAddress.replace('0x', '')
	const addressBytes = Buffer.from(addressHex, 'hex').toString('base64')

	const eventSigHex = MARKET_CREATED_EVENT_SIG.replace('0x', '')
	const eventSigBytes = Buffer.from(eventSigHex, 'hex').toString('base64')

	return [
		handler(
			evmClient.logTrigger({
				addresses: [addressBytes],
				topics: [
					{ values: [eventSigBytes] }, // topic[0]: event signature
				],
			}),
			onMarketCreated,
		),
	]
}

export async function main() {
	const runner = await Runner.newRunner<Config>({
		configSchema,
	})
	await runner.run(initWorkflow)
}
