import React, { Component, useState } from "react";

import ReactDOM from "react-dom";

import WaveSurfer from "wavesurfer.js";
import RegionPlugin from "wavesurfer.js/dist/plugin/wavesurfer.regions.min.js";
import TimelinePlugin from "wavesurfer.js/dist/plugin/wavesurfer.timeline.min.js";

import Container from 'react-bootstrap/Container';
import Button from 'react-bootstrap/Button';
import Collapse from 'react-bootstrap/Collapse';
import Table from 'react-bootstrap/Table';
// import { Collapse, Button} from 'react-bootstrap';
// import {Button, Collapse} from 'react-bootstrap'

import 'bootstrap/dist/css/bootstrap.min.css';
require("./index.css");

// import { unregister } from "registerServiceWorker";

const audioURL = "/api/audio";
const dialogURL = "/api/file/dialog";
const hparamsURL = "/api/file/hparams";


function Header(props) {
  // list hparam entries in a table
  let table = "";
  if (props.state.hparams !== undefined) {
    const hparams = props.state.hparams;
    let listItems = [];
    let key;
    let i=0;
    for (let p in hparams) {
      key = 'hparams'+i.toString();
      listItems.push(
        <tr key={key}> 
          <td>{p}</td> 
          <td>{hparams[p].toString()}</td> 
        </tr>
      )
      i ++;
    }
    if (listItems.length > 0){
      table = (
        <Table responsive striped hover borderless variant="dark" responsive="sm" size="sm" style={{borderRadius: "5px", fontSize: "small"}}>
          <tbody>
          {listItems} 
          </tbody>
        </Table>
      )
    }
  }

  return (
    <Container style={{margin: '10px'}}>
      <h1>Dialog Visualization</h1>
      <div className='row'> 
        <div className='col'> 
          <div className="controls"> 
            <ol style={{listStyleType: 'none'}}>
              <li>
                <input type="checkbox" value="showVad" checked={props.state.showVad} onChange={e => props.onControlChange("vad")}/>
                VAD
              </li>
              <li>
                <input type="checkbox" value="showAsr" checked={props.state.showAsr} onChange={e => props.onControlChange("asr")}/>
                ASR
              </li>
              <li>
                <input type="checkbox" value="showAsr" checked={props.state.showAgentTurn} onChange={e => props.toggleAgentTurn()}/>
                AgentTurnOn
              </li>
              <li>
                <input type="checkbox" value="showAsr" checked={props.state.showTRP} onChange={e => props.toggleTRP()}/>
                All TRP
              </li>
              <li>
                <input type="checkbox" value="showAsr" checked={props.state.showAgentInterrupt} onChange={e => props.toggleAgentInterrupt()}/>
                AgentInterrupted
              </li>
              <li>
                <input type="checkbox" value="showAsr" checked={props.state.showDialogStates} onChange={e => props.toggleDialogStates()}/>
                DialogStates
              </li>
            </ol>
            Zoom <input type="range" min="50" max="300" style={{width: "300px"}} onChange={e => props.onZoom(e)}/>
          </div>
        </div>
        <div className='col' style={{height: "270px", overflowY: 'scroll'}}> 
          {table}
        </div>
      </div>
    </Container >
  );
}

function Turn(props) {
  const [open, setOpen] = useState(false);

  // color 
  let className = "turn-" + props.turn.name;
  const entryStyle = {fontsize: 'small', overflowX: 'auto'}

  let listItems = [];
  if (props.turn !== undefined) {
    let i=0
    let key;
    let val;
    for (let p in props.turn) {
      if (props.turn[p] !== undefined) {
        if (p === 'all_trps'){
          const trp = props.turn.all_trps.map((trp, i) => {
            if (i > 0) {
              return ", " + trp.trp.toString()
            } else {
              return trp.trp.toString()
            }
          })
          listItems.push(
            <li key={key} style={entryStyle}>
              {p}: {trp}
            </li>
          )
        } else {
          listItems.push(
            <li key={key} style={entryStyle}>
              {p}: {props.turn[p].toString()}
            </li>
          )
        }
        i ++;
      }
    }
  }

  return (
    <li key={'turn_' + props.idx} >
      <Button onClick={() => {if (!open) {props.onTimeClick(props.turn.start_time)} setOpen(!open)}} 
        className={'turn ' + className} 
      >
        {props.turn.utterance}
      </Button>
      <Collapse in={open}>
        <ol style={{listStyleType: 'circle'}}>{listItems}</ol>
      </Collapse>
    </li>
  );
}


function Dialog(props) {
  let turns;
  if (props.dialog !== null) {
    turns = props.dialog.turns.map((turn, i) => {
      let side='left';
      if (turn.name === 'agent') {
        side='right'
      }
      return (
        <Turn 
          turn={turn}
          onTimeClick={props.onTimeClick}
          idx={i}
        />
      )
    })
  }
  return (
    <Container >
      <div className="dialog">
        <ol style={{listStyleType: 'none'}}> {turns}</ol>
      </div>
    </Container >
  );
}


class App extends Component {
  constructor(props) {
    super(props);
    this.state = {
      dialog: null,
      showVad: false,
      showAsr: false,
      showAgentTurn: false,
      showTRP: false,
      showAgentInterrupt: false,
      showDialogStates: false,
      playPauseButtonId: 'pause',
      zoom: 50,
    };
    this.onZoom=this.onZoom.bind(this)
    this.onControlChange=this.onControlChange.bind(this)
    this.toggleAgentTurn=this.toggleAgentTurn.bind(this)
    this.toggleTRP=this.toggleTRP.bind(this)
    this.toggleAgentInterrupt=this.toggleAgentInterrupt.bind(this)
    this.toggleDialogStates=this.toggleDialogStates.bind(this)
    this.onTimeClick=this.onTimeClick.bind(this)
  }

  // Waveform + AudioPlayer
  componentDidMount() {
    this.waveform = WaveSurfer.create({
      container: "#audioplayer",
      backend: "WebAudio",
      backgroundColor: "#fafafa",
      scrollParent: true,
      mediaControls: true,
      splitChannels: true,
      splitChannelsOptions: {
        channelColors: {
          0: { progressColor: "darkgreen", waveColor: "#81c784" },
          1: { progressColor: "darkblue", waveColor: "lightblue" },
        },
      },
      height: 200,
      forceDecode: true,
      normalize: true,
      responsive: true,
      plugins: [
        RegionPlugin.create(),
        TimelinePlugin.create({
          container: "#wave-timeline",
    })
      ],
    });
    this.waveform.load(audioURL);
    this.waveform.zoom(this.state.zoom);

    fetch(dialogURL).then(response => response.json()).then((data) => {
      this.setState({dialog: data})
    })
    fetch(hparamsURL).then(response => response.json()).then((data) => {
      this.setState({hparams: data})
      // console.log(data);
    })
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


  onTimeClick(time) {
    this.waveform.backend.media.currentTime = time;
  }

  onZoom(e) {
    this.waveform.zoom(e.target.value);
  };

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

  drawDialogStates(states) {
    let curState, start, end, color;
    for (var i = 0, len = states.length-1; i < len; i++) {
      curState = states[i].state
      start = states[i].time
      end = states[i+1].time
      if (curState === "only_agent") {
        color = "#11aa1110"
      } else if (curState === "only_user") {
        color = "#1111aa10"
      } else if (curState === "silence") {
        color = "#ffffff10"
      } else if (curState === "double_talk") {
        color = "#ff111130"
      }

      this.waveform.addRegion({
        start: start,
        end: end,
        color: color,
        drag: false,
        resize: false,
        id: 'dialogState' + i,
      });
    }
  }

  drawLine (start, color, id, width) {
    this.waveform.addRegion({
      start: start,
      end: start+width,
      color: color,
      drag: false,
      resize: false,
      id: id
    })
  }

  drawLines(arr, color, id, width=0.05) {
    let idd;
    for (var i = 0, len = arr.length; i < len; i++) {
      idd = id + 'Region' + i;
      this.drawLine(arr[i], color, idd, width);
    }
  }

  onClear() {
    let regs = this.waveform.regions.list;
    for (const region in regs) {
      regs[region].remove();
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

  toggleAgentTurn() {
    if (this.state.dialog === null) {
      return;
    }
    if (this.state.showAgentTurn) {
      this.removeRegion('agentTurnOn')
      this.setState({showAgentTurn: false})
    } else {
      this.drawLines(this.state.dialog.agent_turn_on, "#221199", 'agentTurnOn')
      this.setState({showAgentTurn: true})
    };
  }

  toggleAgentInterrupt() {
    if (this.state.dialog === null) {
      return;
    }
    if (this.state.showAgentInterrupt) {
      this.removeRegion('agentInterrupt')
      this.setState({showAgentInterrupt: false})
    } else {
      this.drawLines(this.state.dialog.agent_interrupted, "#99112210", 'agentInterrupt', 0.3)
      this.setState({showAgentInterrupt: true})
    };
  }

  toggleTRP() {
    if (this.state.dialog === null) {
      return;
    }

    if (this.state.showTRP) {
      this.removeRegion('trp')
      this.setState({showTRP: false})
    } else {
      let color;
      let n = 0;
      let trps = [];
      this.setState({showTRP: true})
      this.state.dialog.turns.forEach(turn => {
        if (turn.all_trps !== undefined) {
          turn.all_trps.forEach(trp => {
            if (trp.trp < this.state.hparams.trp) {
              color = "#aa0000"
            } else {
              color = "#00aa00"
            }
            this.drawLine(trp.time, color, 'trp' + n.toString(), 0.05);
            n ++;
          })
        }
      })
    };
  }

  toggleDialogStates() {
    if (this.state.dialog === null) {
      return;
    }
    if (this.state.showDialogStates) {
      this.removeRegion('dialogState')
      this.setState({showDialogStates: false})
    } else {
      this.drawDialogStates(this.state.dialog.dialog_states)
      this.setState({showDialogStates: true})
    };
  }

  onControlChange(name) {
    if (this.state.dialog !== null) {
      if (name === "vad") {
        if (this.state.showVad) {
          this.removeRegion(name+'Region')
          this.setState({showVad: false})
        } else {
          this.drawRegion(this.state.dialog.vad_ipu_on, this.state.dialog.vad_ipu_off, "#81c78430", 'vad')
          this.setState({showVad: true})
        };
      } else if (name === "asr"){
        if (this.state.showAsr) {
          this.removeRegion(name+'Region')
          this.setState({showAsr: false})
        } else {
          this.drawRegion(this.state.dialog.asr_on, this.state.dialog.asr_off, "#28309010", 'asr')
          this.setState({showAsr: true})
        };
      };
    }
  };

  render() {
    return (
      <Container>
        <Header 
          onZoom={this.onZoom}
          onControlChange={this.onControlChange}
          toggleAgentTurn={this.toggleAgentTurn}
          toggleTRP={this.toggleTRP}
          toggleAgentInterrupt={this.toggleAgentInterrupt}
          toggleDialogStates={this.toggleDialogStates}
          state={this.state}
        />
        <div className="media-container">
          <div id="wave-timeline"></div>
          <div id="audioplayer"></div>
          <div className="media-controls">
            <button onClick={() => this.goStart()} className="skip-btn" id="start"></button>
            <button onClick={() => this.playPause()} className="play-btn" id={this.state.playPauseButtonId}></button>
            <button onClick={() => this.goEnd()} className="skip-btn" id="end"></button>
          </div>
        </div>
        <Dialog 
          dialog={this.state.dialog} 
          onTimeClick={this.onTimeClick}
        />
      </Container>
    );
  }
}

ReactDOM.render(<App />, document.getElementById("root"));
