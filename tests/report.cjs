const fs = require('node:fs');
const path = require('node:path');

// Measured release evidence under docs/ is never a default test destination.
exports.writeReport = (name, report) => {
  const output = process.env.SENTINEL_TEST_OUTPUT ||
    path.join('reports', 'local', `${name}-${Date.now()}.json`);
  fs.mkdirSync(path.dirname(output), {recursive: true});
  fs.writeFileSync(output, JSON.stringify(report, null, 2) + '\n', {flag: 'wx'});
  console.log(JSON.stringify({output, ...report}));
};
