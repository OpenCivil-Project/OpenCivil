import { Layout } from "@/components/layout/Layout";
import { HeroSection } from "@/components/home/HeroSection";
import { FeaturesPreview } from "@/components/home/FeaturesPreview";
import { DataFormatSection } from "@/components/home/DataFormatSection";
import { AnalysisEngineSection } from "@/components/home/AnalysisEngineSection";
import { TechSpecs } from "@/components/home/TechSpecs";
import { CTASection } from "@/components/home/CTASection";

const Index = () => {
  return (
    <Layout>
      <HeroSection />
      <FeaturesPreview />
      <DataFormatSection />
      <AnalysisEngineSection />
      <TechSpecs />
      <CTASection />
    </Layout>
  );
};

export default Index;
