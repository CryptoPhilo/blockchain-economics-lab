import { ethers } from 'ethers'

// Supported crypto currencies with their network configs
export const SUPPORTED_CRYPTOS = {
  BTC: {
    name: 'Bitcoin',
    symbol: 'BTC',
    network: 'bitcoin',
    icon: '₿',
    requiredConfirmations: 3,
    // In production, use a BTC payment processor or generate HD wallet addresses
    receivingAddress: process.env.BTC_RECEIVING_ADDRESS || '',
  },
  ETH: {
    name: 'Ethereum',
    symbol: 'ETH',
    network: 'ethereum',
    icon: 'Ξ',
    decimals: 18,
    requiredConfirmations: 12,
    receivingAddress: process.env.ETH_RECEIVING_ADDRESS || '',
  },
  USDT: {
    name: 'Tether USD',
    symbol: 'USDT',
    network: 'ethereum',
    icon: '₮',
    decimals: 6,
    contractAddress: '0xdAC17F958D2ee523a2206206994597C13D831ec7',
    requiredConfirmations: 12,
    receivingAddress: process.env.USDT_RECEIVING_ADDRESS || '',
  },
  USDC: {
    name: 'USD Coin',
    symbol: 'USDC',
    network: 'ethereum',
    icon: '$',
    decimals: 6,
    contractAddress: '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',
    requiredConfirmations: 12,
    receivingAddress: process.env.USDC_RECEIVING_ADDRESS || '',
  },
} as const

export type CryptoCurrency = keyof typeof SUPPORTED_CRYPTOS

// Fetch real-time crypto prices from CoinGecko
export async function getCryptoPrice(currency: CryptoCurrency): Promise<number> {
  const coinIds: Record<CryptoCurrency, string> = {
    BTC: 'bitcoin',
    ETH: 'ethereum',
    USDT: 'tether',
    USDC: 'usd-coin',
  }
  try {
    const res = await fetch(
      `https://api.coingecko.com/api/v3/simple/price?ids=${coinIds[currency]}&vs_currencies=usd`,
      { next: { revalidate: 60 } }
    )
    const data = await res.json()
    return data[coinIds[currency]]?.usd || 0
  } catch {
    // Fallback prices
    const fallback: Record<CryptoCurrency, number> = { BTC: 70000, ETH: 3500, USDT: 1, USDC: 1 }
    return fallback[currency]
  }
}

// Calculate the crypto amount needed for a USD price
export async function calculateCryptoAmount(
  usdCents: number,
  currency: CryptoCurrency
): Promise<{ amount: string; price: number }> {
  const usdAmount = usdCents / 100
  const price = await getCryptoPrice(currency)
  const cryptoAmount = usdAmount / price
  // Round to appropriate precision
  const decimals = currency === 'BTC' ? 8 : currency === 'ETH' ? 6 : 2
  return {
    amount: cryptoAmount.toFixed(decimals),
    price,
  }
}

// Verify an Ethereum transaction (ETH or ERC-20)
export async function verifyEthTransaction(
  txHash: string,
  expectedAmount: string,
  currency: 'ETH' | 'USDT' | 'USDC'
): Promise<{ verified: boolean; confirmations: number }> {
  try {
    const provider = new ethers.JsonRpcProvider(process.env.ETH_RPC_URL || 'https://eth.llamarpc.com')
    const receipt = await provider.getTransactionReceipt(txHash)
    if (!receipt) return { verified: false, confirmations: 0 }

    const currentBlock = await provider.getBlockNumber()
    const confirmations = currentBlock - receipt.blockNumber
    const required = SUPPORTED_CRYPTOS[currency].requiredConfirmations

    return { verified: confirmations >= required, confirmations }
  } catch {
    return { verified: false, confirmations: 0 }
  }
}
