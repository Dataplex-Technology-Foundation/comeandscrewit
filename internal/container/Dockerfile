FROM nginx:alpine

COPY internal/container/nginx.conf /etc/nginx/nginx.conf

# Copy only the publish root. The previous version copied the whole repo and
# then removed four known files by name -- a denylist, and the same defect as
# the old Pages configuration: it shipped README.md, docs/, reference/,
# scripts/ and tests/ into the image, so `docker compose up` served the internal
# material on localhost. An allowlist has nothing to keep in sync.
COPY site/ /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
