import type { Metadata } from "next";
import { headers } from "next/headers";
import "./globals.css";

const title = "Lingua Control · 译员运营台";
const description = "面向本地化团队的译员、费率、PO 与审核受控演示工作台。";

export async function generateMetadata(): Promise<Metadata> {
  const requestHeaders = await headers();
  const host = requestHeaders.get("x-forwarded-host") ?? requestHeaders.get("host") ?? "localhost";
  const protocol = requestHeaders.get("x-forwarded-proto") ?? "https";
  const origin = `${protocol}://${host}`;
  const socialImage = `${origin}/og.png`;

  return {
    metadataBase: new URL(origin),
    title,
    description,
    applicationName: "Lingua Control",
    openGraph: {
      type: "website",
      url: origin,
      locale: "zh_CN",
      siteName: "Lingua Control",
      title,
      description,
      images: [{ url: socialImage, width: 1732, height: 908, alt: "Lingua Control 译员运营台" }],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [socialImage],
    },
  };
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
