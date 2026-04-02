// Bootstrap: tunnel http2 connections through HTTP CONNECT proxy.
// Solves the "model provider doesn't serve your region" error for Cursor CLI.
"use strict";
(() => {
  const proxyUrl =
    process.env.HTTPS_PROXY || process.env.HTTP_PROXY ||
    process.env.https_proxy || process.env.http_proxy;
  if (!proxyUrl || !proxyUrl.startsWith("http://")) return;

  const net = require("net");
  const tls = require("tls");
  const http2 = require("http2");
  const { Duplex } = require("stream");
  const { URL } = require("url");

  let pHost, pPort;
  try {
    const p = new URL(proxyUrl);
    pHost = p.hostname;
    pPort = parseInt(p.port, 10) || 7890;
  } catch (_) { return; }

  function makeDuplexPair() {
    let s1, s2;
    s1 = new Duplex({
      read() {},
      write(chunk, _enc, cb) { s2.push(chunk); cb(); },
      final(cb) { s2.push(null); cb(); },
    });
    s2 = new Duplex({
      read() {},
      write(chunk, _enc, cb) { s1.push(chunk); cb(); },
      final(cb) { s1.push(null); cb(); },
    });
    s1.remoteAddress = pHost;
    s1.remotePort = pPort;
    s2.remoteAddress = pHost;
    s2.remotePort = pPort;
    return [s1, s2];
  }

  const origConnect = http2.connect;

  http2.connect = function (authority, options, listener) {
    let target;
    try {
      target = new URL(typeof authority === "string" ? authority : authority.toString());
    } catch (_) {
      return origConnect.call(this, authority, options, listener);
    }

    if (target.protocol !== "https:" || target.hostname === pHost ||
        target.hostname === "127.0.0.1" || target.hostname === "localhost") {
      return origConnect.call(this, authority, options, listener);
    }

    const targetHost = target.hostname;
    const targetPort = parseInt(target.port, 10) || 443;

    const mergedOpts = Object.assign({}, options || {}, {
      createConnection(_auth, _opts) {
        const [clientSide, serverSide] = makeDuplexPair();

        // Asynchronously set up the CONNECT tunnel + TLS.
        const proxySocket = net.createConnection(pPort, pHost, () => {
          proxySocket.write(
            `CONNECT ${targetHost}:${targetPort} HTTP/1.1\r\n` +
            `Host: ${targetHost}:${targetPort}\r\n\r\n`
          );
        });

        let headerBuf = "";
        proxySocket.on("data", function onData(chunk) {
          headerBuf += chunk.toString("latin1");
          const endIdx = headerBuf.indexOf("\r\n\r\n");
          if (endIdx === -1) return;
          proxySocket.removeListener("data", onData);

          if (!headerBuf.match(/^HTTP\/1\.[01] 200/)) {
            clientSide.destroy(new Error("CONNECT failed: " + headerBuf.slice(0, 80)));
            proxySocket.destroy();
            return;
          }

          const remaining = Buffer.from(headerBuf.slice(endIdx + 4), "latin1");

          // Wrap the tunneled socket in TLS.
          const tlsSocket = tls.connect({
            socket: proxySocket,
            servername: targetHost,
            ALPNProtocols: ["h2"],
          });

          if (remaining.length > 0) {
            tlsSocket.unshift(remaining);
          }

          tlsSocket.on("secureConnect", () => {
            // Bidirectional pipe between clientSide and tlsSocket.
            serverSide.on("data", (d) => tlsSocket.write(d));
            serverSide.on("end", () => tlsSocket.end());
            tlsSocket.on("data", (d) => serverSide.write(d));
            tlsSocket.on("end", () => serverSide.end());
            tlsSocket.on("error", (e) => clientSide.destroy(e));
            serverSide.on("error", (e) => tlsSocket.destroy(e));
          });

          tlsSocket.on("error", (e) => {
            clientSide.destroy(e);
            proxySocket.destroy();
          });
        });

        proxySocket.on("error", (e) => clientSide.destroy(e));

        return clientSide;
      },
    });

    return origConnect.call(this, authority, mergedOpts, listener);
  };
})();
