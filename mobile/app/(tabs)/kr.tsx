import { SafeAreaView, ScrollView, Text, View } from 'react-native';
import { PriceCard } from '../../components/PriceCard';
import { SignalBadge } from '../../components/SignalBadge';
import { TradeList } from '../../components/TradeList';
import { useSignals } from '../../hooks/useSignals';
import { useAllocationOverview, useRegimeOverview } from '../../hooks/useOverview';

export default function KrScreen() {
  const { data } = useSignals('kr');
  const { data: allocation } = useAllocationOverview();
  const { data: regime } = useRegimeOverview();
  const picks = data?.top_picks || [];
  const avgMl = picks.length
    ? picks.reduce((sum: number, item: any) => sum + Number(item.ml_confidence || 0), 0) / picks.length
    : 0;
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: '#f3efe4' }}>
      <ScrollView contentContainerStyle={{ padding: 18, gap: 14 }}>
        <PriceCard
          title="KR Picks"
          value={`${picks.length}`}
          subtitle={`Allocation ${Number(allocation?.kr_pct || 0).toFixed(1)}%`}
          accent="#1f4d7a"
        />
        <View style={{ flexDirection: 'row', gap: 10 }}>
          <SignalBadge label={`Updated ${data?.updated_at ? 'OK' : 'PENDING'}`} tone="neutral" />
          <SignalBadge label={`Regime ${regime?.current_regime || data?.regime || 'TRANSITION'}`} tone="neutral" />
          <SignalBadge label={`Avg ML ${avgMl.toFixed(0)}%`} tone={avgMl >= 70 ? 'good' : 'neutral'} />
        </View>
        <View style={{ backgroundColor: '#fffaf0', borderRadius: 22, padding: 18, gap: 12 }}>
          <Text style={{ fontSize: 18, fontWeight: '700', color: '#112b1f' }}>Top Picks</Text>
          {picks.slice(0, 5).map((item: any) => (
            <View key={item.ticker} style={{ borderTopWidth: 1, borderTopColor: '#ece3d4', paddingTop: 12 }}>
              <Text style={{ fontWeight: '700', color: '#1a2d24' }}>{item.ticker} {item.name ? `· ${item.name}` : ''}</Text>
              <Text style={{ color: '#4d5c51', marginTop: 4 }}>Score {item.score} | ML {Number(item.ml_confidence || 0).toFixed(1)}%</Text>
              <Text style={{ color: '#6a756d', marginTop: 4 }}>Action {item.action || 'WATCH'}</Text>
            </View>
          ))}
        </View>
        <TradeList title="Factor Snapshot" items={picks.map((item: any) => `${item.ticker}: ${Object.keys(item.factors || {}).length} factors`).slice(0, 5)} />
      </ScrollView>
    </SafeAreaView>
  );
}
