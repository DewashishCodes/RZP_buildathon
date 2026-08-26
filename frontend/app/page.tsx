import { Hero } from "@/components/landing/hero";
import { ProofStrip } from "@/components/landing/proof-strip";
import { Pipeline } from "@/components/landing/pipeline";
import { GuardrailProof } from "@/components/landing/guardrail-proof";
import { ChannelLadder } from "@/components/landing/channel-ladder";
import { Breadth } from "@/components/landing/breadth";
import { Credibility } from "@/components/landing/credibility";
import { Postmortem } from "@/components/landing/postmortem";
import { FinalCta } from "@/components/landing/final-cta";
import { ThresholdDivider } from "@/components/landing/threshold-divider";

export default function Home() {
  return (
    <div>
      <Hero />

      <div className="mx-auto flex max-w-5xl flex-col gap-16 px-6 py-16">
        <section className="flex flex-col gap-4">
          <h2 className="font-numeric text-center text-[11px] uppercase tracking-wider text-text-muted">
            Measured, not simulated away
          </h2>
          <ProofStrip />
        </section>

        <ThresholdDivider />
        <Pipeline />

        <ThresholdDivider />
        <GuardrailProof />

        <ThresholdDivider />
        <ChannelLadder />

        <ThresholdDivider />
        <Breadth />

        <ThresholdDivider />
        <Credibility />

        <ThresholdDivider />
        <Postmortem />

        <ThresholdDivider />
        <FinalCta />
      </div>
    </div>
  );
}
