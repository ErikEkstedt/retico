import React, { Component } from "react";
import WaveSurfer from "wavesurfer.js";
import RegionPlugin from "wavesurfer.js/dist/plugin/wavesurfer.regions.min.js";
import TimelinePlugin from "wavesurfer.js/dist/plugin/wavesurfer.timeline.min.js";

import { Container, Row, Col } from 'react-bootstrap';
import './App.css';

const audioURL = "/api/audio";
const dialogURL = "/api/dialog";
const interactionURL = "/api/interaction"


export default class DialogAudio extends Component {
  constructor(props) {
    super(props);
    this.state = {
      dialogData: null,
      hparams: null,
      name: "agent",
      channels: props.channels,
      id: props.id,
      showVad: false,
      showAsr: false,
      showTRP: false,
      showTFO: false,
      showTurnStart: false,
      showTurnEnd: false,
      showInterrupt: false,
      showFallback: false,
      showDialogStates: false,
      showAgentTurn: false,
      playPauseButtonId: 'pause',
      colorUser: {tfo: "#8855dd", vad: "#99dd77", audio: "lightblue"},
      colorAgent: {tfo: "#aa5555", vad: "#99dd77", audio: "#99dd77"},
      zoom: 50,
    };
    this.onTimeClick=this.onTimeClick.bind(this)
  }

  // Waveform + AudioPlayer
  componentDidMount() {
    this.waveform = WaveSurfer.create({
      container: "#audioplayer-"+this.state.id,
      backend: "WebAudio",
      backgroundColor: "#fafafa",
      scrollParent: true,
      mediaControls: true,
      splitChannels: true,
      partialRender: true,
      splitChannelsOptions: {
        channelColors: {
          0: { progressColor: "darkgreen", waveColor: this.state.colorAgent.audio },
          1: { progressColor: "darkblue", waveColor: this.state.colorUser.audio },
        }
      },
      height: this.props.wavHeight,
      forceDecode: true,
      normalize: true,
      responsive: true,
      plugins: [
        RegionPlugin.create(),
        TimelinePlugin.create({
          container: "#wave-timeline-"+this.state.id,
    })
      ],
    });
    if (this.props.interaction !== ""){
      this.waveform.load(audioURL+"/"+this.props.interaction);
      this.waveform.zoom(this.state.zoom);
      fetch(interactionURL+'/hparams/'+this.props.interaction).then(response => response.json()).then((data) => {
        console.log('hparams: ', data)
        this.setState({
          hparams: data,
        })
      })
      fetch(dialogURL+'/'+this.props.interaction).then(response => response.json()).then((data) => {
        this.setState({
          dialogData: true,
          vad: data.vad,
          asr: data.asr,
          tfo: data.tfo,
          trp: data.trp,
          fallback: data.fallback,
          interruption: data.interruption,
          turn_starts: data.turn_starts,
          turn_ends: data.turn_ends,
        })
      })
    }
  }

  playPause() {
    if (this.state.playing) {
      this.waveform.pause()
      this.setState({playing: false, playPauseButtonId: "pause"})
    } else {
      this.waveform.play()
      this.setState({playing: true, playPauseButtonId: "play"})
    }
  }
  goStart() {
    // this.waveform.skipBackward(10)
    this.waveform.seekAndCenter(0)
  }
  goEnd() {
    // this.waveform.skipForward(10)
    this.waveform.seekAndCenter(1)
  }
  onZoom(e) {
    this.waveform.zoom(e.target.value);
  };
  onTimeClick(time) {
    this.waveform.backend.media.currentTime = time;
  }

  // Draw on waveform
  drawRegion(a, b, color, id) {
    for (var i = 0, len = a.length; i < len; i++) {
      this.waveform.addRegion({
        start: a[i],
        end: b[i],
        color: color,
        drag: false,
        resize: false,
        id: id + 'Region' + i,
      });
    }
  }

  removeRegion(id) {
    let regs = this.waveform.regions.list;
    for (const region in regs) {
      if (regs[region].id.includes(id)) {
        regs[region].remove();
      };
    }
  };

  drawLine (start, color, id, width) {
    if (start >= 0 ) {
      this.waveform.addRegion({
        start: start,
        end: start+width,
        color: color,
        drag: false,
        resize: false,
        id: id
      })
    } else {
      console.log('start line: ' + start);
    }
  }

  drawLines(arr, color, id, width=0.05) {
    let idd;
    for (var i = 0, len = arr.length; i < len; i++) {
      idd = id + 'Region' + i;
      this.drawLine(arr[i], color, idd, width);
    }
  }

  // Checkboxes
  toggleVad() {
    console.log('toggleVad')
    if (this.state.dialogData === null) {
      return;
    }
    if (this.state.showVad) {
      this.removeRegion('vad')
      this.setState({showVad: false})
    } else {
      this.drawRegion(this.state.vad.on, this.state.vad.off, this.state.colorUser.vad+"30", 'vad')
      this.setState({showVad: true})
    };
  }
  toggleAsr() {
    console.log('toggleAsr');
    if (this.state.dialogData === null) {
      return;
    }
    if (this.state.showAsr) {
      this.removeRegion('asr')
      this.setState({showAsr: false})
    } else {
      this.drawRegion(this.state.asr.on, this.state.asr.off, "#28309010", 'asr')
      this.setState({showAsr: true})
    };
  }

  toggleTRP() {
    console.log('toggleTRP')
    if (this.state.dialogData === null) {
      return;
    }
    if (this.state.showTRP) {
      this.setState({showTRP: false})
      this.removeRegion('trp')
    } else {
      this.setState({showTRP: true})
      let n = 0;
      this.state.trp.forEach((trp, time) => {
        let color = "#00aa00";
        if (trp.trp < this.state.hparams.trp) {
          color = "#aa0000"
        }
        this.drawLine(trp.time, color, 'trp' + n.toString(), 0.03);
        n ++;
      })
    }
  };
  toggleInterrupt() {
    console.log('ToggleInterrupt')
    if (this.state.dialogData === null) {
      return;
    }
    if (this.state.showInterrupt) {
      this.removeRegion('Interrupt')
      this.setState({showInterrupt: false})
    } else {
      this.drawLines(this.state.interruption, "#eba01b50", 'Interrupt', .2)
      this.setState({showInterrupt: true})
    };
  }
  toggleFallback() {
    console.log('ToggleFallback')
    if (this.state.dialogData === null) {
      return;
    }
    if (this.state.showFallback) {
      this.removeRegion('fallback')
      this.setState({showFallback: false})
    } else {
      this.drawLines(this.state.fallback, "#ab005050", 'fallback', .2)
      this.setState({showFallback: true})
    };
  }
  toggleTFO() {
    console.log('toggleTFO')
    if (this.state.dialogData === null) {
      return;
    }
    if (this.state.showTFO) {
      this.removeRegion('tfo-agent')
      this.removeRegion('tfo-user')
      this.setState({showTFO: false})
    } else {
      this.drawRegion(this.state.tfo.agent.starts, this.state.tfo.agent.ends, this.state.colorAgent.tfo+"30", 'tfo-agent')
      this.drawRegion(this.state.tfo.user.starts, this.state.tfo.user.ends, this.state.colorUser.tfo+"30", 'tfo-user')
      this.setState({showTFO: true})
    };
  }
  toggleTurnStart() {
    console.log('toggleTurnStart')
    if (this.state.dialogData === null) {
      return;
    }
    if (this.state.showTurnStart) {
      this.removeRegion('turnstarts-agent')
      this.removeRegion('turnstarts-user')
      this.setState({showTurnStart: false})
    } else {
      this.drawLines(this.state.turn_starts.agent, '#000000', 'turnstarts-agent', .02)
      this.drawLines(this.state.turn_starts.user, '#000000', 'turnstarts-user', .02)
      this.setState({showTurnStart: true})
    };
  }
  toggleTurnEnd() {
    console.log('toggleTurnEnd')
    if (this.state.dialogData === null) {
      return;
    }
    if (this.state.showTurnEnd) {
      this.removeRegion('turnends-agent')
      this.removeRegion('turnends-user')
      this.setState({showTurnEnd: false})
    } else {
      this.drawLines(this.state.turn_ends.agent, this.state.colorAgent.tfo, 'turnends-agent', 0.02)
      this.drawLines(this.state.turn_ends.user, this.state.colorUser.tfo, 'turnends-user', 0.02)
      this.setState({showTurnEnd: true})
    };
  }

  render() {
    return (
      <Container fluid style={{background: '#eaeaea'}}>
          <div id={"wave-timeline-"+this.state.id}></div>
          <div id={"audioplayer-"+this.state.id}></div>
          <Row className="controls" style={{padding: '20px'}}>
            <Col className="controls-checkbox">
              <Row>
                <label className='checkbox-label'>
                  <input type="checkbox" value="showVad" checked={this.state.showVad} onChange={e => this.toggleVad()}/>
                  Vad {" "}
                </label>
                <label className='checkbox-label'>
                  <input type="checkbox" value="showAsr" checked={this.state.showAsr} onChange={e => this.toggleAsr()}/>
                  ASR{" "}
                </label>
                <label className='checkbox-label'>
                  <input type="checkbox" value="showTRP" checked={this.state.showTRP} onChange={e => this.toggleTRP()}/>
                  TRP{" "}
                </label>
                <label className='checkbox-label'>
                  <input type="checkbox" value="showInterrupt" checked={this.state.showInterrupt} onChange={e => this.toggleInterrupt()}/>
                  Interrupt
                </label>
                <label className='checkbox-label'>
                  <input type="checkbox" value="showFallback" checked={this.state.showFallback} onChange={e => this.toggleFallback()}/>
                  Fallback
                </label>
                <label className='checkbox-label'>
                  <input type="checkbox" value="showTFO" checked={this.state.showTFO} onChange={e => this.toggleTFO()}/>
                  TFO
                </label>
              </Row>
              <Row>
                <label className='checkbox-label'>
                  <input type="checkbox" value="showTurnStart" checked={this.state.showTurnStart} onChange={e => this.toggleTurnStart()}/>
                  Turn Starts{" "}
                </label>
                <label className='checkbox-label'>
                  <input type="checkbox" value="showTurnEnd" checked={this.state.showTurnEnd} onChange={e => this.toggleTurnEnd()}/>
                  Turn Ends{" "}
                </label>
              </Row>
            </Col>
            <Col md="auto" className="controls-media">
              <div>
                <button onClick={() => this.goStart()} className="skip-btn" id="start"></button>
                <button onClick={() => this.playPause()} className="play-btn" id={this.state.playPauseButtonId}></button>
                <button onClick={() => this.goEnd()} className="skip-btn" id="end"></button>
                <input type="range" min="50" max="300" onChange={e => this.onZoom(e)}/>
              </div>
            </Col>
          </Row>
      </Container>
    );
  }
}
