import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "GeoWeather Intelligence Platform - Real-time Weather GIS",
  description: "End-to-End Real-Time GIS & Weather Analytics Platform using Flink, Kafka, PostGIS, Deck.gl, and Next.js.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <link rel="icon" href="/favicon.ico" />
      </head>
      <body>
        {children}
      </body>
    </html>
  );
}
