import { SafeAreaView, ScrollView, Text, View } from 'react-native';
import { PriceCard } from '../../components/PriceCard';
import { SignalBadge } from '../../components/SignalBadge';
import { TradeList } from '../../components/TradeList';
import { useSignals } from '../../hooks/useSignals';
import { useAllocationOverview, useRegimeOverview } from '../../hooks/useOverview';

export default function UsScreen() {
  const { data } = useSignals('us');
  const { data: allocation } = useAllocationOverview();
  const { data: regime } = useRegimeOverview();
  const picks = data?.top_picks || [];
  const avgScore = picks.length
    ? picks.reduce((sum: number, item: any) => sum + Number(item.momentum_score || 0), 0) / picks.length
    : 0;
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: '#f3efe4' }}>
      <ScrollView contentContainerStyle={{ padding: 18, gap: 14 }}>
        <PriceCard
          title="US Momentum"
          value={`${picks.length}`}
          subtitle={`Allocation ${Number(allocation?.us_pct || 0).toFixed(1)}%`}
          accent="#0f6a55"
        />
        <View style={{ flexDirection: 'row', gap: 10 }}>
          <SignalBadge label={`Updated ${data?.updated_at ? 'OK' : 'PENDING'}`} tone="neutral" />
          <SignalBadge label={`Regime ${regime?.current_regime || data?.regime || 'TRANSITION'}`} tone="neutral" />
          <SignalBadge label={`Avg Score ${avgScore.toFixed(0)}`} tone={avgScore >= 70 ? 'good' : 'neutral'} />
        </View>
        <TradeList
          title="Momentum Ranking"
          items={picks.slice(0, 5).map((item: any) => `${item.ticker} · ${Number(item.momentum_score || 0).toFixed(0)} · ${item.grade || '-'}`)}
        />
      </ScrollView>
    </SafeAreaView>
  );
}
