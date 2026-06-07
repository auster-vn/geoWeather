FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY go.mod ./
COPY main.go ./
RUN go build -o gateway main.go

FROM alpine:latest
WORKDIR /app
COPY --from=builder /app/gateway .
ENV PORT=8080
ENV API_TARGET=http://api:8000
EXPOSE 8080
CMD ["./gateway"]
