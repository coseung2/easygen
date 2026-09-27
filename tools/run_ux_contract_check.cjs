const fs = require('node:fs')
const path = require('node:path')
const ts = require('typescript')

function load(relativePath) {
  const filename = path.resolve(__dirname, relativePath)
  const source = fs.readFileSync(filename, 'utf8')
  const output = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, strict: true },
    fileName: filename,
  }).outputText.replaceAll("require('../src/ux/contractCheck')", "require('./src/ux/contractCheck')")
    .replaceAll("require('./contract')", "require('./contract')")
  const module = { exports: {} }
  const dirname = path.dirname(filename)
  new Function('exports', 'require', 'module', '__filename', '__dirname', output)(
    module.exports,
    (request) => {
      if (request.startsWith('./') || request.startsWith('../')) return load(path.join(path.relative(__dirname, dirname), request.replace(/\.js$/, '') + '.ts'))
      return require(request)
    },
    module,
    filename,
    dirname,
  )
  return module.exports
}

const { contractCheckReport } = load('./check_ux_contract.ts')
const report = contractCheckReport()
console.log(report)
if (report !== 'UX contract check passed') process.exit(1)
