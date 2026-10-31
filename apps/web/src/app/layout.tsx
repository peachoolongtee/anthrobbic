import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { MotionProvider } from "@/components/motion-provider";

// Atkinson Hyperlegible keeps look-alike characters apart (0 and O, 1, l and
// I, B and 8), which matters when reading flight numbers, gates and runways.
// Vendored in ./fonts (SIL Open Font License) so the app needs no network at
// build or run time. globals.css (shadcn) maps Tailwind's font-sans to --font-sans.
const sans = localFont({
  src: "./fonts/AtkinsonHyperlegibleNext-Variable.woff2",
  variable: "--font-sans",
  weight: "200 800",
  display: "swap",
});

const mono = localFont({
  src: "./fonts/AtkinsonHyperlegibleMono-Variable.woff2",
  variable: "--font-atkinson-mono",
  weight: "200 800",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Magic Airbuzz",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`dark ${sans.variable} ${mono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        <MotionProvider>{children}</MotionProvider>
      </body>
    </html>
  );
}
