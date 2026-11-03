ARG NODE_IMAGE
ARG PYTHON_IMAGE
FROM ${NODE_IMAGE} AS node
FROM ${PYTHON_IMAGE}
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx
WORKDIR /opt/mammoth-ui
COPY ui/mad-architecht-command-center/package.json ui/mad-architecht-command-center/package-lock.json ./ui/
RUN cd ui && npm ci --no-audit --no-fund && rm -rf /root/.npm
COPY package.json package-lock.json ./tests/
RUN cd tests && npm ci --no-audit --no-fund \
    && PLAYWRIGHT_BROWSERS_PATH=/opt/mammoth-ui/browsers npx playwright install --with-deps chromium \
    && chmod -R a+rX /opt/mammoth-ui/browsers && rm -rf /root/.npm \
    && touch /opt/mammoth-ui/browser-ready
COPY scripts/owner-ui/validate.mjs ./
COPY scripts/owner-ui/browser.config.cjs ./
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/mammoth-ui/browsers
USER 65534:65534
WORKDIR /work
