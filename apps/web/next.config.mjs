/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  allowedDevOrigins: ['127.0.0.1'],
  async rewrites() {
    const apiOrigin = process.env.REELSTRUCT_API_ORIGIN || 'http://127.0.0.1:8010'
    return [
      {
        source: '/api/:path*',
        destination: `${apiOrigin}/api/:path*`,
      },
      {
        source: '/downloads/:path*',
        destination: `${apiOrigin}/downloads/:path*`,
      },
      {
        source: '/output/:path*',
        destination: `${apiOrigin}/output/:path*`,
      },
    ]
  },
}

export default nextConfig
