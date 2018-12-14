const WebSocket = require('ws');
const http = require('http');
const request = require('request');

const client = require('prom-client');
const redis = require('redis');

const register = client.register;

const port = 3000;

const requestHandler = (request, response) => {
  response.end(register.metrics())
}

const server = http.createServer(requestHandler)
const redis_client = redis.createClient();

redis_client.on("error", function (err) {
    console.log("Error " + err);
});

server.listen(port, (err) => {
  if (err) {
    return console.log('something bad happened', err)
  }

  console.log(`server is listening on ${port}`)
})


const hosts = [
  ['host1', [8001, 8002]],
];

const logins = [
  ["username", "hunter2"]
];

const sentGauge = new client.Gauge({
  name: 'sent',
  help: 'sent data in bytes',
  labelNames: ['host', 'port', 'version']
});
const receivedGauge = new client.Gauge({
  name: 'received',
  help: 'received data in bytes',
  labelNames: ['host', 'port', 'version']
});
const sendingGauge = new client.Gauge({
  name: 'sending',
  help: 'sending data in bytes',
  labelNames: ['host', 'port', 'version']
});
const receivingGauge = new client.Gauge({
  name: 'receiving',
  help: 'receiving data in bytes',
  labelNames: ['host', 'port', 'version']
});

hosts.forEach((host_port) => {
  var host = host_port[0];
  var ports = host_port[1];

  ports.forEach((port) => {
    const ws = new WebSocket(`ws://${host}:${port}/1/1/websocket`);

    ws.on('close', () => {
      console.log('close')
      process.exit(1)
    })

    ws.on('error', (err) => {
      console.log('ERROR', err)
      process.exit(1)
    })

    function bytesToSize(bytes) {
       var sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
       if (bytes == 0) return '0 Byte';
       var i = parseInt(Math.floor(Math.log(bytes) / Math.log(1024)));
       return Math.round(bytes / Math.pow(1024, i), 2) + ' ' + sizes[i];
    };

    let version = 'unknown'
    const get_version = (callback) => {
      for (let loginpair of logins) {
        let username = loginpair[0];
        let password = loginpair[1];
        let foundLine = false;

        if (foundLine) {
          break;
        }

        request({
          url:`http://${host}:${port}/api/help`,
          auth: {user: username, pass: password}
        }, (err, res, body) => {
          if (err) console.log(err)
          body.split('\n').forEach((line) => {
            if (line.indexOf('Cloning version') !== -1) {
              foundLine = true
              version = line.split(' ')[9]
              console.log('got version ' + version)
              if (callback) {
                callback();
              }
            }
          })
          if (!foundLine) {
            if (!body.match("Authentication Required")) {
              console.log(host, port, body);
            }
          }
        });
      }
    }

    setInterval(get_version, 1000 * 60);

    get_version(() => {
      sentGauge.set({host, port, version}, 0)
      receivedGauge.set({host, port, version}, 0)
      sendingGauge.set({host, port, version}, 0)
      receivingGauge.set({host, port, version}, 0)
      ws.on('message', function incoming(data) {
        try {
          const parsed = JSON.parse(JSON.parse(data.substring(1))[0])
          if (parsed.event_name === 'bandwidth') {
            const {received, sent} = parsed.message
            const {receiving, sending} = parsed.message
            sentGauge.set({host, port, version}, sent)
            receivedGauge.set({host, port, version}, received)
            sendingGauge.set({host, port, version}, sending)
            receivingGauge.set({host, port, version}, receiving)
          } else if (parsed.event_name == 'item.output') {
            var new_message = JSON.parse(JSON.stringify(parsed.message));
            new_message.host = host;
            new_message.port = port;

            redis_client.publish("tumblr:warrior", JSON.stringify(new_message));
          }
        } catch (err) {
          console.log(data, err)
        }
      })
    })
  })
})