var express = require('express'),
    app = express();

app.use(express.static('public'));

var server = app.listen(8080);
