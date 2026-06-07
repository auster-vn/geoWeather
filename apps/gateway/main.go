package main

import (
	"log"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
)

func main() {
	targetURL := os.Getenv("API_TARGET")
	if targetURL == "" {
		targetURL = "http://api:8000"
	}
	
	target, err := url.Parse(targetURL)
	if err != nil {
		log.Fatalf("Invalid API_TARGET URL: %v", err)
	}

	proxy := httputil.NewSingleHostReverseProxy(target)

	// Add CORS headers and forward SSE
	proxy.ModifyResponse = func(r *http.Response) error {
		r.Header.Set("Access-Control-Allow-Origin", "*")
		r.Header.Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		r.Header.Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
		return nil
	}

	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		// Handle preflight CORS
		if r.Method == "OPTIONS" {
			w.Header().Set("Access-Control-Allow-Origin", "*")
			w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
			w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
			w.WriteHeader(http.StatusOK)
			return
		}
		
		log.Printf("Proxying request: %s %s", r.Method, r.URL.Path)
		proxy.ServeHTTP(w, r)
	})

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	log.Printf("Golang API Gateway listening on :%s, routing to %s", port, targetURL)
	log.Fatal(http.ListenAndServe(":"+port, nil))
}
