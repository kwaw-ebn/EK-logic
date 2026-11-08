import { NextRequest } from "next/server";
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
const MAX_BODY = 11 * 1024 * 1024;
async function proxy(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  const target = `${process.env.API_INTERNAL_URL || "http://127.0.0.1:8000"}/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`;
  const headers = new Headers();
  for (const key of ["cookie", "content-type", "origin", "x-ek-request"]) {
    const value = request.headers.get(key);
    if (value) headers.set(key, value);
  }
  let body: Uint8Array | undefined;
  if (!["GET", "HEAD"].includes(request.method) && request.body) {
    const chunks: Uint8Array[] = [];
    let size = 0;
    const reader = request.body.getReader();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > MAX_BODY) {
        await reader.cancel();
        return Response.json(
          { detail: "Maximum file size is 10 MB" },
          { status: 413 },
        );
      }
      chunks.push(value);
    }
    body = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) {
      body.set(chunk, offset);
      offset += chunk.byteLength;
    }
  }
  try {
    const upstream = await fetch(target, {
      method: request.method,
      headers,
      body: body as BodyInit | undefined,
      redirect: "manual",
      cache: "no-store",
      signal: AbortSignal.timeout(120000),
    });
    const outputHeaders = new Headers({ "Cache-Control": "no-store" });
    for (const key of [
      "content-type",
      "content-disposition",
      "set-cookie",
      "location",
      "x-content-type-options",
    ]) {
      const value = upstream.headers.get(key);
      if (value) outputHeaders.set(key, value);
    }
    return new Response(upstream.body, {
      status: upstream.status,
      headers: outputHeaders,
    });
  } catch {
    return Response.json(
      { detail: "The analytics service is unavailable. Please retry shortly." },
      { status: 502 },
    );
  }
}
export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const DELETE = proxy;
