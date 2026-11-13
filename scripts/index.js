'use strict';

module.exports = {
  ...require('./lib/install'),
  init: require('./init').run,
  upgrade: require('./upgrade').run,
};
