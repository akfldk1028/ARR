import { readFileSync, rmSync } from 'node:fs'
import path from 'node:path'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import electron from 'vite-plugin-electron/simple'
import pkg from './package.json'




// https://vitejs.dev/config/
export default defineConfig(({ command, mode }) => {
  const webOnly = !!process.env.WEB_ONLY || mode === 'web'
  if (!webOnly) rmSync('dist-electron', { recursive: true, force: true })

  const isServe = command === 'serve'
  const isBuild = command === 'build'
  const sourcemap = isServe || !!process.env.VSCODE_DEBUG
  const env = loadEnv(mode, process.cwd(), '')
  const arrBackendUrl = env.VITE_ARR_BACKEND_URL || 'http://127.0.0.1:18000'
  const proxyApiUrl = env.VITE_PROXY_URL || 'http://127.0.0.1:3001'
  return {
    resolve: {
      alias: {
        '@': path.join(__dirname, 'src'),
        '@stackframe/react': path.join(__dirname, 'src/types/stackframe-react-stub.ts'),
      },
      dedupe: ['react', 'react-dom'],
    },
    plugins: [
      react(),
      ...(!webOnly ? [electron({
        main: {
          // Shortcut of `build.lib.entry`
          entry: 'electron/main/index.ts',
          onstart(args) {
            if (process.env.VSCODE_DEBUG) {
              console.log(/* For `.vscode/.debug.script.mjs` */'[startup] Electron App')
            } else {
              args.startup()
            }
          },
          vite: {
            build: {
              sourcemap,
              minify: isBuild,
              outDir: 'dist-electron/main',
              rollupOptions: {
                external: Object.keys('dependencies' in pkg ? pkg.dependencies : {}),
              },
            },
          },
        },
        preload: {
          // Shortcut of `build.rollupOptions.input`.
          // Preload scripts may contain Web assets, so use the `build.rollupOptions.input` instead `build.lib.entry`.
          input: 'electron/preload/index.ts',
          vite: {
            build: {
              sourcemap: sourcemap ? 'inline' : undefined, // #332
              minify: isBuild,
              outDir: 'dist-electron/preload',
              rollupOptions: {
                external: Object.keys('dependencies' in pkg ? pkg.dependencies : {}),
              },
            },
          },
        },
        // Ployfill the Electron and Node.js API for Renderer process.
        // If you want use Node.js in Renderer process, the `nodeIntegration` needs to be enabled in the Main process.
        // See 👉 https://github.com/electron-vite/vite-plugin-electron-renderer
        renderer: {},
      })] : []),
    ],
    server: {
      open: false,
      proxy: {
        // Django backend (law, land, agents)
        // bypass: HTML page requests → SPA fallback, API/JSON requests → Django
        '/law': {
          target: arrBackendUrl,
          changeOrigin: true,
          bypass(req) {
            if (req.headers.accept?.includes('text/html')) return '/index.html'
          },
        },
        '/land': {
          target: arrBackendUrl,
          changeOrigin: true,
          bypass(req) {
            if (req.headers.accept?.includes('text/html')) return '/index.html'
          },
        },
        '/design': {
          target: arrBackendUrl,
          changeOrigin: true,
          bypass(req) {
            if (req.headers.accept?.includes('text/html')) return '/index.html'
          },
        },
        '/agents': { target: arrBackendUrl, changeOrigin: true },
        // AutoGen Studio (when VSCODE_DEBUG)
        '/api': { target: proxyApiUrl, changeOrigin: true },
      },
      ...(process.env.VSCODE_DEBUG && (() => {
        const url = new URL(pkg.debug.env.VITE_DEV_SERVER_URL)
        return {
          host: url.hostname,
          port: +url.port,
        }
      })()),
      clearScreen: false,
    }
  }
})

process.on('SIGINT', () => {
  try {
    const backend = path.join(__dirname, 'backend')
    const pid = readFileSync(backend + '/runtime/run.pid', 'utf-8')
    process.kill(parseInt(pid), 'SIGINT')
  } catch (e) {
    console.log('no pid file')
    console.log(e)
  }
})
