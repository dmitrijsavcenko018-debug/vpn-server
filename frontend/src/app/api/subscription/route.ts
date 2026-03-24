import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({
    status: "active",
    expiresAt: "2026-12-31T23:59:59.000Z",
    connectUrl: "https://sector14.app/connect/mock-link"
  });
}
