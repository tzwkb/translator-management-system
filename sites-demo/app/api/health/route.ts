export async function GET(): Promise<Response> {
  return new Response(
    JSON.stringify({ status: "ok", service: "lingua-control-demo" }),
    {
      status: 200,
      headers: { "content-type": "application/json" },
    },
  );
}
