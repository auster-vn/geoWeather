import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "GeoWeather — Bản đồ & Trợ lý Thời tiết AI",
  description: "Hệ thống GIS & Phân tích Thời tiết Real-Time kết hợp AI. Tìm kiếm thời tiết, dự báo mưa, UV, và chọn tuyến đường an toàn.",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "GeoWeather",
  },
  icons: {
    apple: "/icon-192.png",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  viewportFit: "cover",
  themeColor: "#0B1220",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi" data-theme="light" suppressHydrationWarning>
      <head>
        <link rel="icon" href="/favicon.ico" />
        <link rel="apple-touch-icon" href="/icon-192.png" />
        {/* Restore theme before paint to avoid flash */}
        <script dangerouslySetInnerHTML={{ __html: `
          (function(){
            var t = localStorage.getItem('geoweather-theme');
            document.documentElement.setAttribute('data-theme', t === 'dark' ? 'dark' : 'light');
          })()
        `}} />
      </head>
      <body>
        {children}
      </body>
    </html>
  );
}
