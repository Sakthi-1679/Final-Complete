
import React, { useState, useRef, useEffect } from 'react';
import { detectLiveMood, getMoodBasedMovies } from '../services/ai';
import { saveFeedback } from '../services/storage';
import { logUserEvent } from '../services/logger';
import { Movie, MoodType } from '../types';
import MovieCard from './MovieCard';

const MoodSearch: React.FC = () => {
  const [liveStatus, setLiveStatus] = useState<'idle' | 'listening' | 'analyzing' | 'error' | 'initializing' | 'denied' | 'waiting'>('waiting');
  const [result, setResult] = useState<{ mood: MoodType; reasoning: string; movies: Movie[] } | null>(null);
  
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const loopTimeoutRef = useRef<number | null>(null);

  // Attempt to start automatically, but respect browser's need for interaction
  useEffect(() => {
    const attemptAutoStart = async () => {
      // Check if permissions might already be granted
      try {
        const result = await navigator.permissions.query({ name: 'camera' as any });
        if (result.state === 'granted') {
          requestPermissions();
        }
      } catch (e) {
        // navigator.permissions.query might not be supported for camera in all browsers
        console.debug("Permission query not supported, waiting for user interaction");
      }
    };
    attemptAutoStart();
    
    return () => stopLiveDetection();
  }, []);

  const requestPermissions = async () => {
    try {
      setLiveStatus('initializing');
      
      const stream = await navigator.mediaDevices.getUserMedia({ 
        video: { width: { ideal: 640 }, height: { ideal: 480 } }, 
        audio: true 
      });
      
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.onloadedmetadata = () => {
          videoRef.current?.play().catch(e => console.error("Video play failed:", e));
        };
      }
      
      setLiveStatus('idle');
      runDetectionLoop();
    } catch (err: any) {
      console.error("Sensor Access Error:", err);
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError' || err.name === 'NotFoundError') {
        setLiveStatus('denied');
      } else {
        setLiveStatus('error');
      }
    }
  };

  const stopLiveDetection = () => {
    if (loopTimeoutRef.current) clearTimeout(loopTimeoutRef.current);
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    setLiveStatus('waiting');
  };

  const runDetectionLoop = async () => {
    if (!streamRef.current) return;

    try {
      setLiveStatus('listening');
      const imageB64 = captureFrame();
      const audioB64 = await recordAudio(3000);
      
      setLiveStatus('analyzing');
      if (imageB64 && audioB64) {
        const analysis = await detectLiveMood(imageB64, audioB64);
        if (analysis) {
          logUserEvent('MOOD_PREDICTION', { mood: analysis.mood, confidence: analysis.confidence });
          const movies = getMoodBasedMovies(analysis.mood);
          setResult({ mood: analysis.mood, reasoning: analysis.reasoning, movies });
        }
      }

      setLiveStatus('idle');
    } catch (error) {
      console.error("Detection Loop Error:", error);
      setLiveStatus('idle');
    }

    loopTimeoutRef.current = window.setTimeout(runDetectionLoop, 10000);
  };

  const captureFrame = (): string | null => {
    if (!videoRef.current || !canvasRef.current) return null;
    const context = canvasRef.current.getContext('2d');
    if (!context) return null;
    
    canvasRef.current.width = videoRef.current.videoWidth || 640;
    canvasRef.current.height = videoRef.current.videoHeight || 480;
    context.drawImage(videoRef.current, 0, 0);
    
    return canvasRef.current.toDataURL('image/jpeg', 0.8).split(',')[1];
  };

  const recordAudio = (ms: number): Promise<string | null> => {
    return new Promise((resolve) => {
      if (!streamRef.current) return resolve(null);
      
      try {
        const recorder = new MediaRecorder(streamRef.current);
        const chunks: Blob[] = [];
        
        recorder.ondataavailable = (e) => {
          if (e.data.size > 0) chunks.push(e.data);
        };
        
        recorder.onstop = async () => {
          if (chunks.length === 0) return resolve(null);
          const blob = new Blob(chunks, { type: 'audio/webm' });
          const reader = new FileReader();
          reader.onloadend = () => {
            const base64 = (reader.result as string).split(',')[1];
            resolve(base64);
          };
          reader.readAsDataURL(blob);
        };
        
        recorder.start();
        setTimeout(() => {
          if (recorder.state === 'recording') recorder.stop();
        }, ms);
      } catch (e) {
        console.error("Audio recording failed:", e);
        resolve(null);
      }
    });
  };

  const handleFeedback = (liked: boolean) => {
    if (result) {
      saveFeedback({
        mood: result.mood,
        recommendedMovies: result.movies,
        feedback: liked ? 'positive' : 'negative'
      });
      alert(liked ? "Glad you liked the match!" : "Thanks for the feedback, we'll improve.");
    }
  };

  if (liveStatus === 'waiting' || liveStatus === 'denied' || liveStatus === 'error') {
    return (
      <div className="px-4 md:px-12 py-12 text-center bg-netflix-dark animate-fade-in">
        <div className="max-w-2xl mx-auto bg-netflix-card/50 p-12 rounded-[2rem] border border-white/10 backdrop-blur-2xl shadow-2xl relative overflow-hidden group">
          {/* Decorative background pulse */}
          <div className="absolute -top-24 -left-24 w-48 h-48 bg-netflix-red/10 rounded-full blur-3xl animate-pulse"></div>
          <div className="absolute -bottom-24 -right-24 w-48 h-48 bg-blue-500/10 rounded-full blur-3xl animate-pulse delay-700"></div>

          <div className="w-24 h-24 bg-gradient-to-tr from-netflix-red/20 to-netflix-red/5 rounded-3xl flex items-center justify-center mx-auto mb-8 transform group-hover:rotate-12 transition-transform duration-500 shadow-inner">
            <i className={`fas ${liveStatus === 'denied' ? 'fa-lock' : liveStatus === 'error' ? 'fa-exclamation-triangle' : 'fa-video'} text-netflix-red text-4xl`}></i>
          </div>
          
          <h2 className="text-3xl font-black text-white mb-4 tracking-tight">
            {liveStatus === 'denied' ? 'Access Required' : liveStatus === 'error' ? 'Sensor Error' : 'Neural Discovery Ready'}
          </h2>
          
          <p className="text-gray-400 mb-10 leading-relaxed text-lg font-medium max-w-md mx-auto">
            {liveStatus === 'denied' 
              ? 'Permissions were denied. To use AI mood discovery, please enable camera and microphone access in your browser settings.' 
              : liveStatus === 'error'
              ? 'Something went wrong accessing your sensors. Please ensure your camera and microphone are properly connected.'
              : 'Our Vision AI curates a unique stream by sensing your micro-expressions and vocal tone in real-time.'}
          </p>
          
          <div className="flex flex-col space-y-4">
            <button 
              onClick={requestPermissions}
              className="w-full px-8 py-5 bg-netflix-red text-white font-black rounded-2xl hover:bg-netflix-redHover transition-all hover:scale-[1.02] active:scale-95 shadow-[0_10px_40px_rgba(229,9,20,0.3)] text-lg flex items-center justify-center group"
            >
              <i className="fas fa-bolt mr-3 group-hover:animate-bounce"></i>
              Enable AI Sensing
            </button>
            <p className="text-[11px] text-gray-500 uppercase tracking-widest font-bold">
              Privacy First: Processing occurs locally, nothing is stored.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="px-4 md:px-12 py-8 bg-gradient-to-b from-black/50 to-transparent min-h-[500px]">
      <div className="max-w-4xl mx-auto">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-10 gap-4">
          <div>
            <h2 className="text-2xl md:text-3xl font-bold text-white mb-2 flex items-center">
              <i className="fas fa-brain text-netflix-red mr-3 animate-pulse"></i>
              Real-time Vision AI
            </h2>
            <p className="text-gray-400">
              Personalizing your feed based on your micro-expressions and tone.
            </p>
          </div>
          <div className="flex items-center space-x-2 text-netflix-red bg-netflix-red/10 px-5 py-2.5 rounded-full border border-netflix-red/20 shadow-[0_0_15px_rgba(229,9,20,0.15)]">
             <span className="w-2 h-2 bg-netflix-red rounded-full animate-pulse"></span>
             <span className="text-[10px] font-bold uppercase tracking-[0.2em]">Sensor Active</span>
          </div>
        </div>

        <div className="flex flex-col md:flex-row gap-10 items-center bg-netflix-card/40 p-10 rounded-[2.5rem] border border-white/5 backdrop-blur-xl animate-zoom-in shadow-2xl overflow-hidden group">
          <div className="relative w-64 h-64 rounded-full overflow-hidden border-4 border-netflix-red/40 shadow-2xl flex-shrink-0 bg-black group-hover:border-netflix-red/60 transition-colors">
             <video 
              ref={videoRef} 
              autoPlay 
              muted 
              playsInline 
              className="w-full h-full object-cover scale-x-[-1]" 
             />
             <canvas ref={canvasRef} className="hidden" />
             
             <div className="absolute inset-0 pointer-events-none z-10">
                <div className="w-full h-1 bg-netflix-red/80 shadow-[0_0_15px_#E50914] absolute top-0 animate-[scan_3s_linear_infinite]"></div>
                <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent"></div>
             </div>
             
             <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-20">
                <div className={`px-4 py-1.5 rounded-full text-[9px] font-bold uppercase tracking-[0.15em] flex items-center space-x-2 shadow-2xl backdrop-blur-md border border-white/10 ${
                  liveStatus === 'analyzing' ? 'bg-blue-600/80' : 
                  liveStatus === 'listening' ? 'bg-orange-600/80' : 
                  liveStatus === 'initializing' ? 'bg-gray-700/80' : 
                  'bg-green-600/80'
                }`}>
                  <span className={`w-2 h-2 rounded-full bg-white ${['analyzing', 'listening', 'initializing'].includes(liveStatus) ? 'animate-pulse' : ''}`}></span>
                  <span>{liveStatus}</span>
                </div>
             </div>
          </div>

          <div className="flex-1 text-center md:text-left">
            <div className="mb-4">
              <span className="text-netflix-red font-mono text-xs font-bold uppercase tracking-[0.4em] mb-2 block">Detection Pipeline v3.2</span>
              <h3 className="text-4xl font-extrabold text-white mb-4 tracking-tight">Neural Sync</h3>
            </div>
            <p className="text-gray-400 max-w-sm leading-relaxed text-sm font-medium">
              Streaming analytics engine processing multimodal data every 10s. Your expressions guide the curation logic instantly.
            </p>
            
            <div className="mt-8 flex flex-wrap gap-3 justify-center md:justify-start">
              <span className="text-[9px] bg-white/5 px-3 py-1.5 rounded-lg text-gray-400 font-mono uppercase border border-white/5">Voice Tone</span>
              <span className="text-[9px] bg-white/5 px-3 py-1.5 rounded-lg text-gray-400 font-mono uppercase border border-white/5">Face Landmarks</span>
              <span className="text-[9px] bg-white/5 px-3 py-1.5 rounded-lg text-gray-400 font-mono uppercase border border-white/5">Gemini 3 Flash</span>
            </div>
          </div>
        </div>

        {result && (
          <div className="mt-12 animate-slide-up" key={result.mood}>
            <div className="bg-netflix-card/90 backdrop-blur-2xl p-8 rounded-2xl border border-gray-800 mb-8 flex flex-col md:flex-row items-center justify-between shadow-2xl relative overflow-hidden group">
              <div className="absolute top-0 left-0 w-1.5 h-full bg-netflix-red"></div>
              <div className="max-w-xl">
                <div className="flex items-center space-x-3 mb-3">
                  <span className="text-netflix-red text-xs font-bold uppercase tracking-[0.2em]">Neural Match Found</span>
                  <div className="h-[1px] w-8 bg-gray-700"></div>
                </div>
                <div className="flex items-center mb-3">
                  <span className="text-white font-black text-4xl capitalize">
                    {result.mood}
                  </span>
                  <span className="ml-4 flex items-center justify-center w-12 h-12 rounded-full bg-white/5 text-2xl">
                    {result.mood === 'happy' && '😊'}
                    {result.mood === 'sad' && '😢'}
                    {result.mood === 'stressed' && '🤯'}
                    {result.mood === 'angry' && '🔥'}
                    {result.mood === 'calm' && '🌿'}
                  </span>
                </div>
                <p className="text-gray-400 italic text-sm leading-relaxed">"{result.reasoning}"</p>
              </div>
              <div className="mt-8 md:mt-0 flex flex-col items-center">
                <span className="text-[10px] text-gray-500 mb-4 font-bold uppercase tracking-[0.25em]">Quality Signal</span>
                <div className="flex space-x-4">
                  <button onClick={() => handleFeedback(true)} className="w-14 h-14 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center text-gray-400 hover:text-green-500 hover:border-green-500/50 hover:bg-green-500/5 transition-all hover:scale-105 active:scale-95 shadow-xl">
                    <i className="fas fa-thumbs-up text-lg"></i>
                  </button>
                  <button onClick={() => handleFeedback(false)} className="w-14 h-14 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center text-gray-400 hover:text-red-500 hover:border-red-500/50 hover:bg-red-500/5 transition-all hover:scale-105 active:scale-95 shadow-xl">
                    <i className="fas fa-thumbs-down text-lg"></i>
                  </button>
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between mb-8">
              <h3 className="text-2xl font-black text-white flex items-center tracking-tight">
                <span className="w-10 h-[2px] bg-netflix-red mr-4"></span>
                AI Recommended Stream
              </h3>
              <div className="flex items-center text-[10px] text-gray-500 font-bold uppercase tracking-widest bg-white/5 px-3 py-1.5 rounded-full border border-white/5">
                <span className="w-1.5 h-1.5 bg-netflix-red rounded-full mr-2 animate-pulse"></span>
                Refreshing
              </div>
            </div>
            
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-5">
              {result.movies.map(movie => (
                <MovieCard key={movie.id} movie={movie} className="w-full hover:z-20" />
              ))}
            </div>
          </div>
        )}
      </div>
      
      <style>{`
        @keyframes scan {
          0% { top: -5%; opacity: 0; }
          15% { opacity: 1; }
          85% { opacity: 1; }
          100% { top: 105%; opacity: 0; }
        }
      `}</style>
    </div>
  );
};

export default MoodSearch;
