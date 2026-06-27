import type { NextApiRequest, NextApiResponse } from 'next'

export const config = {
  api: {
    bodyParser: true,
  },
}

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  const backendUrl = process.env.BACKEND_URL || 'http://localhost:8080'
  const path = req.url?.split('?')[0]?.replace(/^\/api/, '') || ''
  const url = `${backendUrl}/api${path}${req.url?.includes('?') ? req.url.split('?')[1] : ''}`

  try {
    const response = await fetch(url, {
      method: req.method,
      headers: {
        'Content-Type': 'application/json',
        ...(req.headers.authorization ? { Authorization: req.headers.authorization } : {}),
      },
      body: req.method !== 'GET' && req.method !== 'HEAD' ? JSON.stringify(req.body) : undefined,
    })

    const data = await response.json()
    res.status(response.status).json(data)
  } catch (error) {
    res.status(500).json({ error: 'Proxy request failed' })
  }
}
