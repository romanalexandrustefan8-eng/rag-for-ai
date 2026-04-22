import { useState } from 'react';
import { LawCard } from '@/components/LawCard';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Menu, X, Search } from 'lucide-react';

/**
 * Design System: Professional Minimalism with Regulatory Precision
 * Simplified Romanian version - Focus on NEW LAWS with RAG-powered summaries
 */

interface LawData {
  id: string;
  title: string;
  category: string;
  fullText: string; // Full law text for RAG processing
  minCompliance: number;
  maxCompliance: number;
  currentCompliance: number;
  complianceThreshold: number;
  isNew: boolean;
  datePublished: string;
}

const NEW_FINANCIAL_LAWS: LawData[] = [
  {
    id: '1',
    title: 'Reglementări Noi Anti-Spălare de Bani (AML) 2024',
    category: 'AML',
    fullText: `Reglementări Noi Anti-Spălare de Bani (AML) 2024

Articolul 1: Definiții și Domeniu de Aplicare
Prezenta reglementare se aplică tuturor instituțiilor financiare, inclusiv băncilor, caselor de schimb, prestatorilor de servicii de plată și altor entități care gestionează fonduri sau valori mobiliare.

Articolul 2: Obligații de Raportare
Instituțiile financiare trebuie să raporteze orice tranzacții suspecte în termen de 24 de ore către Unitatea de Informații Financiare (UIF).

Articolul 3: Verificarea Beneficiarului Real
Instituțiile trebuie să verifice identitatea beneficiarului real al tuturor conturilor și să actualizeze informațiile anual.

Articolul 4: Sancțiuni
Nerespectarea acestor reglementări poate duce la amenzi de până la 500.000 EUR și suspendarea licenței.

Data Intrării în Vigoare: 1 martie 2024`,
    minCompliance: 0,
    maxCompliance: 100,
    currentCompliance: 85,
    complianceThreshold: 80,
    isNew: true,
    datePublished: '2024-02-15',
  },
  {
    id: '2',
    title: 'Cerințe Noi Cunoaștere Client (KYC) Îmbunătățite',
    category: 'Bancar',
    fullText: `Cerințe Noi Cunoaștere Client (KYC) Îmbunătățite

Articolul 1: Verificare Digitală
Instituțiile financiare pot utiliza metode de verificare digitală pentru identificarea clienților, inclusiv recunoașterea facială și verificarea documentelor.

Articolul 2: Informații Necesare
Trebuie colectate: nume complet, adresă, ocupație, sursă de venit, scop al relației și beneficiar real.

Articolul 3: Actualizare Periodică
Informațiile KYC trebuie actualizate anual sau atunci când se detectează modificări semnificative.

Articolul 4: Excepții
Excepții se aplică pentru microîntreprinderi cu venituri sub 100.000 EUR anual.

Data Intrării în Vigoare: 1 aprilie 2024`,
    minCompliance: 0,
    maxCompliance: 100,
    currentCompliance: 72,
    complianceThreshold: 85,
    isNew: true,
    datePublished: '2024-03-10',
  },
  {
    id: '3',
    title: 'Reglementări Noi pentru Tranzacții cu Valori Mobiliare',
    category: 'Valori Mobiliare',
    fullText: `Reglementări Noi pentru Tranzacții cu Valori Mobiliare

Articolul 1: Transparență și Raportare
Toți brokerii trebuie să raporteze zilnic volumele de tranzacții și prețurile medii.

Articolul 2: Prevenirea Manipulării Pieței
Interzicerea tranzacțiilor cu informații privilegiate și a manipulării artificiale a prețurilor.

Articolul 3: Protecția Investitorului
Instituțiile trebuie să mențină fonduri de protecție pentru investitori în caz de insolvență.

Articolul 4: Audit Intern
Auditurile interne trebuie efectuate trimestrial de firme independente.

Data Intrării în Vigoare: 1 mai 2024`,
    minCompliance: 0,
    maxCompliance: 100,
    currentCompliance: 90,
    complianceThreshold: 85,
    isNew: true,
    datePublished: '2024-04-05',
  },
  {
    id: '4',
    title: 'Obligații Noi de Raportare Fiscală pentru Instituții Financiare',
    category: 'Fiscal',
    fullText: `Obligații Noi de Raportare Fiscală pentru Instituții Financiare

Articolul 1: Raportare Electronică
Toate rapoartele fiscale trebuie transmise electronic prin portalul ANAF.

Articolul 2: Informații Detaliate
Rapoartele trebuie să conțină detalii despre fiecare client și tranzacție peste 10.000 EUR.

Articolul 3: Termene de Raportare
Rapoartele lunare trebuie transmise până pe 15 a lunii următoare.

Articolul 4: Penalități
Întârzierile în raportare atrag penalități de 500 EUR pe zi.

Data Intrării în Vigoare: 1 iunie 2024`,
    minCompliance: 0,
    maxCompliance: 100,
    currentCompliance: 78,
    complianceThreshold: 85,
    isNew: true,
    datePublished: '2024-05-20',
  },
  {
    id: '5',
    title: 'Norme Noi de Protecție a Datelor pentru Sector Financiar',
    category: 'Bancar',
    fullText: `Norme Noi de Protecție a Datelor pentru Sector Financiar

Articolul 1: Criptare Obligatorie
Toate datele sensibile trebuie criptate atât în tranzit cât și în repaus.

Articolul 2: Audit de Securitate
Auditurile de securitate trebuie efectuate anual de firme externe certificate.

Articolul 3: Notificare Breșelor
Breșele de date trebuie raportate în termen de 72 de ore.

Articolul 4: Drepturi ale Clienților
Clienții au dreptul să acceseze, să corecteze și să șteargă datele lor personale.

Data Intrării în Vigoare: 1 iulie 2024`,
    minCompliance: 0,
    maxCompliance: 100,
    currentCompliance: 82,
    complianceThreshold: 85,
    isNew: true,
    datePublished: '2024-06-15',
  },
];

export default function Home() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [lawData, setLawData] = useState<LawData[]>(NEW_FINANCIAL_LAWS);

  const categories = Array.from(new Set(NEW_FINANCIAL_LAWS.map((law) => law.category)));

  const filteredLaws = lawData.filter((law) => {
    const matchesSearch =
      law.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      law.fullText.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesCategory = !selectedCategory || law.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  const handleComplianceChange = (lawId: string, newCompliance: number) => {
    setLawData((prev) =>
      prev.map((law) =>
        law.id === lawId ? { ...law, currentCompliance: newCompliance } : law
      )
    );
  };

  const overallCompliance =
    Math.round(
      (lawData.reduce((sum, law) => sum + law.currentCompliance, 0) / lawData.length) * 100
    ) / 100;

  const compliantCount = lawData.filter(
    (law) => law.currentCompliance >= law.complianceThreshold
  ).length;

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-40 border-b border-border bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/60">
        <div className="container flex items-center justify-between h-16">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="lg:hidden p-2 hover:bg-secondary rounded-lg transition-colors"
            >
              {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
                <span className="text-white font-bold text-sm">⚖️</span>
              </div>
              <h1 className="text-xl font-bold text-foreground">Legi Noi</h1>
            </div>
          </div>

          {/* Overall Compliance Badge */}
          <div className="flex items-center gap-4">
            <div className="hidden sm:flex flex-col items-end text-sm">
              <span className="text-muted-foreground text-xs">Conformitate Generală</span>
              <span className="text-lg font-bold text-primary">{overallCompliance}%</span>
            </div>
            <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center">
              <span className="text-primary font-semibold text-sm">{compliantCount}/{lawData.length}</span>
            </div>
          </div>
        </div>
      </header>

      <div className="flex">
        {/* Sidebar */}
        <aside
          className={`fixed inset-y-16 left-0 z-30 w-64 border-r border-border bg-card transition-transform duration-300 lg:relative lg:inset-auto lg:z-0 lg:translate-x-0 ${
            sidebarOpen ? 'translate-x-0' : '-translate-x-full'
          }`}
        >
          <div className="p-6 space-y-6">
            {/* Search */}
            <div>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  type="text"
                  placeholder="Cauta legi..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10 h-9"
                />
              </div>
            </div>

            {/* Category Filter */}
            <div>
              <h3 className="text-sm font-semibold text-foreground mb-3">Categorii</h3>
              <div className="space-y-2">
                <button
                  onClick={() => setSelectedCategory(null)}
                  className={`w-full text-left px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                    selectedCategory === null
                      ? 'bg-primary text-primary-foreground'
                      : 'text-foreground hover:bg-secondary'
                  }`}
                >
                  Toate legile noi
                </button>
                {categories.map((category) => (
                  <button
                    key={category}
                    onClick={() => setSelectedCategory(category)}
                    className={`w-full text-left px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                      selectedCategory === category
                        ? 'bg-primary text-primary-foreground'
                        : 'text-foreground hover:bg-secondary'
                    }`}
                  >
                    {category}
                  </button>
                ))}
              </div>
            </div>

            {/* Stats */}
            <div className="pt-4 border-t border-border">
              <h3 className="text-sm font-semibold text-foreground mb-3">Statistici</h3>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Conforme</span>
                  <span className="font-semibold text-green-600">{compliantCount}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Necesită Revizuire</span>
                  <span className="font-semibold text-amber-600">{lawData.length - compliantCount}</span>
                </div>
              </div>
            </div>

            {/* Info Box */}
            <div className="pt-4 border-t border-border bg-primary/5 rounded-lg p-3">
              <p className="text-xs text-muted-foreground">
                <strong>💡 Sfat:</strong> Rezumatele legilor sunt generate automat de un model RAG. Consultați textul complet pentru detalii juridice precise.
              </p>
            </div>
          </div>
        </aside>

        {/* Main Content */}
        <main className="flex-1 min-h-[calc(100vh-4rem)]">
          {/* Simple Hero Section */}
          <div className="bg-gradient-to-r from-primary/10 to-primary/5 border-b border-border py-8">
            <div className="container">
              <h2 className="text-3xl font-bold text-foreground mb-2">Legi Financiare Noi 2024</h2>
              <p className="text-muted-foreground max-w-2xl">
                Urmăriți și gestionați conformitatea cu noile reglementări financiare. Rezumatele sunt generate automat de un model RAG pentru ușurință de înțelegere.
              </p>
            </div>
          </div>

          {/* Laws Grid */}
          <div className="container py-12">
            {/* Grid Header */}
            <div className="mb-8">
              <h3 className="text-2xl font-bold text-foreground mb-2">
                {selectedCategory ? `Legi Noi - ${selectedCategory}` : 'Toate Legile Noi'}
              </h3>
              <p className="text-muted-foreground">
                {filteredLaws.length} din {lawData.length} legi afișate
              </p>
            </div>

            {/* Laws Grid */}
            {filteredLaws.length > 0 ? (
              <div className="law-grid">
                {filteredLaws.map((law) => (
                  <LawCard
                    key={law.id}
                    {...law}
                    onComplianceChange={(value) => handleComplianceChange(law.id, value)}
                  />
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <div className="w-16 h-16 rounded-full bg-secondary flex items-center justify-center mb-4">
                  <span className="text-2xl">🔍</span>
                </div>
                <h4 className="text-lg font-semibold text-foreground mb-2">Nicio lege găsită</h4>
                <p className="text-muted-foreground">Încercați să ajustați criteriile de căutare sau filtru</p>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
