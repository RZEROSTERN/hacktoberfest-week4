import net from 'node:net'

function listen(server: net.Server): Promise<number> {
  return new Promise((resolve, reject) => {
    server.once('error', reject)
    server.listen(0, '127.0.0.1', () => resolve((server.address() as net.AddressInfo).port))
  })
}

function close(server: net.Server): Promise<void> {
  return new Promise(resolve => server.close(() => resolve()))
}

/** Two different free loopback ports. The first stays reserved while the second is picked. */
export async function twoFreePorts(): Promise<[number, number]> {
  const a = net.createServer()
  const b = net.createServer()
  try {
    const first = await listen(a)
    const second = await listen(b)
    return [first, second]
  } finally {
    await Promise.all([close(a), close(b)])
  }
}
