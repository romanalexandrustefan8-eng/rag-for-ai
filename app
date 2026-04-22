import React, { useState, useEffect } from 'react';
import { View, Text, Button, FlatList, ActivityIndicator, Alert, StyleSheet, TouchableOpacity } from 'react-native';
import CryptoJS from 'crypto-js';

/**
 * LegisRo Mobile Template
 * Integrate this into your React Native project.
 * Ensure you have 'crypto-js' installed: npm install crypto-js
 */

const LawMobileApp = () => {
  const [laws, setLaws] = useState([]);
  const [loading, setLoading] = useState(true);
  const [hashes, setHashes] = useState({});

  const API_URL = 'https://ais-dev-mw3vauu26s6n3lul5hhshf-479509175523.europe-west2.run.app'; // Replace with your production URL

  // 1. Fetch Approved Legislative Archive
  useEffect(() => {
    fetch(`${API_URL}/api/laws`)
      .then(response => response.json())
      .then(data => {
        setLaws(data);
        setLoading(false);
      })
      .catch(error => {
        console.error(error);
        Alert.alert("Eroare", "Nu s-au putut prelua datele legislative.");
        setLoading(false);
      });
  }, []);

  // 2. Security: Document Verification Hashes (Calculated locally for integrity)
  useEffect(() => {
    const newHashes = {};
    laws.forEach((law) => {
      // Hash the sensitive parts of the law for local integrity verification
      const dataToHash = JSON.stringify({ id: law.id, title: law.title, obligations: law.obligations });
      const hash = CryptoJS.SHA256(dataToHash).toString();
      newHashes[law.id] = hash;
    });
    setHashes(newHashes);
  }, [laws]);

  const requestClarification = (lawId) => {
    // Send a 'Human Review' request for a specific law if users find it unclear
    fetch(`${API_URL}/api/admin/review-request`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lawId, userId: 'mobile_user_test', reason: 'Unclear wording' }),
    })
    .then(() => Alert.alert("Succes", "Cererea de clarificare a fost trimisă către un expert."))
    .catch(err => Alert.alert("Eroare", "Cererea nu a putut fi trimisă."));
  };

  const renderLawItem = ({ item }) => (
    <View style={styles.lawCard}>
      <View style={styles.header}>
        <Text style={styles.category}>{item.category}</Text>
        <Text style={styles.date}>{new Date(item.publishDate).toLocaleDateString()}</Text>
      </View>
      <Text style={styles.title}>{item.title}</Text>
      <Text style={styles.summary} numberOfLines={3}>{item.summary}</Text>
      
      <View style={styles.actionRow}>
        <TouchableOpacity 
          style={styles.detailsButton}
          onPress={() => Alert.alert(item.title, item.simplifiedText)}
        >
          <Text style={styles.buttonText}>Vezi Detalii</Text>
        </TouchableOpacity>
        
        <TouchableOpacity 
          style={styles.reviewButton}
          onPress={() => requestClarification(item.id)}
        >
          <Text style={styles.reviewButtonText}>Cerere Clarificare</Text>
        </TouchableOpacity>
      </View>
      
      <Text style={styles.hashText}>Hash Integritate: {hashes[item.id]?.substring(0, 16)}...</Text>
    </View>
  );

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#1A2B3C" />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.headerTitle}>FiscalClar Mobile</Text>
      <FlatList
        data={laws}
        keyExtractor={(item) => item.id}
        renderItem={renderLawItem}
        contentContainerStyle={styles.list}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f8f9fa', paddingTop: 60 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  headerTitle: { fontSize: 24, fontWeight: 'bold', textAlign: 'center', color: '#1A2B3C', marginBottom: 20 },
  list: { padding: 15 },
  lawCard: { backgroundColor: '#fff', borderRadius: 15, padding: 15, marginBottom: 15, elevation: 3, shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.1, shadowRadius: 4 },
  header: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 10 },
  category: { color: '#2D5A27', fontWeight: 'bold', fontSize: 12 },
  date: { color: '#6c757d', fontSize: 12 },
  title: { fontSize: 18, fontWeight: 'bold', color: '#1A2B3C', marginBottom: 5 },
  summary: { fontSize: 14, color: '#495057', marginBottom: 15 },
  actionRow: { flexDirection: 'row', gap: 10 },
  detailsButton: { flex: 1, backgroundColor: '#1A2B3C', padding: 12, borderRadius: 8, alignItems: 'center' },
  reviewButton: { flex: 1, borderColor: '#1A2B3C', borderWidth: 1, padding: 12, borderRadius: 8, alignItems: 'center' },
  buttonText: { color: '#fff', fontWeight: 'bold' },
  reviewButtonText: { color: '#1A2B3C', fontWeight: 'bold' },
  hashText: { fontSize: 10, color: '#ced4da', marginTop: 10, fontStyle: 'italic' }
});

export default LawMobileApp;
