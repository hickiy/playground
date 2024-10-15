const fs = require("fs")
const path = require("path")

const svelte = require('svelte/compiler');
const source = fs.readFileSync(path.resolve(__dirname, "App.svelte"), "utf8")

const result = svelte.compile(source, {
	filename: 'index.js',
  generate: 'dom',
  sveltePath: '..',
});



fs.writeFileSync(path.resolve(__dirname, "build/index.js"), result.js.code)




