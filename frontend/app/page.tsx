export default function HomePage() {
  return (
    <main style={{ maxWidth: 720, margin: "4rem auto", padding: "0 1.5rem" }}>
      <h1>VitalStream</h1>
      <p>Distributed Wearable Health Insights Platform — patient & coach dashboard.</p>
      <p style={{ opacity: 0.7 }}>
        This is a scaffold. Login, device binding, and the insights/trends views described in the
        PRD (section 3.3) still need to be built against the API at{" "}
        <code>{process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}</code>.
      </p>
    </main>
  );
}
