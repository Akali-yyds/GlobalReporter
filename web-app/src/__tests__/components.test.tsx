/**
 * Tests for news stores
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { useNewsStore } from '../stores/newsStore';
import { useGlobeStore } from '../stores/globeStore';

describe('News Store', () => {
  beforeEach(() => {
    // Reset store state before each test
    useNewsStore.setState({
      events: [
        { id: '1', title: 'Test Event 1', heat_score: 100, main_country: 'CN' } as any,
        { id: '2', title: 'Test Event 2', heat_score: 200, main_country: 'US' } as any,
      ],
      selectedEvent: null,
      isLoading: false,
      error: null,
      total: 2,
      page: 1,
      pageSize: 20,
    });
  });

  it('has correct initial state after setup', () => {
    const store = useNewsStore.getState();
    
    expect(store.events).toBeDefined();
    expect(store.events.length).toBe(2);
    expect(store.selectedEvent).toBeNull();
    expect(store.isLoading).toBe(false);
    expect(store.error).toBeNull();
  });

  it('can set selected event', () => {
    const store = useNewsStore.getState();
    const event = store.events[0];
    
    useNewsStore.getState().setSelectedEvent(event);
    
    const updatedStore = useNewsStore.getState();
    expect(updatedStore.selectedEvent).toEqual(event);
  });

  it('can clear selected event', () => {
    const store = useNewsStore.getState();
    const event = store.events[0];
    
    useNewsStore.getState().setSelectedEvent(event);
    useNewsStore.getState().setSelectedEvent(null);
    
    const updatedStore = useNewsStore.getState();
    expect(updatedStore.selectedEvent).toBeNull();
  });

  it('renders event count correctly', () => {
    const store = useNewsStore.getState();
    expect(store.events.length).toBe(2);
  });

  it('displays events with correct data', () => {
    const store = useNewsStore.getState();
    const firstEvent = store.events[0];
    
    expect(firstEvent.id).toBe('1');
    expect(firstEvent.title).toBe('Test Event 1');
    expect(firstEvent.heat_score).toBe(100);
  });
});

describe('Globe Store', () => {
  beforeEach(() => {
    // Reset store state before each test
    useGlobeStore.setState({
      hotspots: [],
      globeRotation: true,
      currentScope: 'all',
    });
  });

  it('has correct initial state', () => {
    const store = useGlobeStore.getState();
    
    expect(store.hotspots).toBeDefined();
    expect(store.hotspots).toEqual([]);
    expect(store.globeRotation).toBe(true);
    expect(store.currentScope).toBe('all');
  });

  it('can toggle rotation', () => {
    const initialStore = useGlobeStore.getState();
    const initialRotation = initialStore.globeRotation;
    
    useGlobeStore.getState().toggleRotation();
    
    const updatedStore = useGlobeStore.getState();
    expect(updatedStore.globeRotation).toBe(!initialRotation);
  });

  it('can set scope', () => {
    useGlobeStore.getState().setScope('china');
    
    const updatedStore = useGlobeStore.getState();
    expect(updatedStore.currentScope).toBe('china');
  });
});
