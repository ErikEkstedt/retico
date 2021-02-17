import React, { Component, useState } from "react";

import ReactDOM from "react-dom";

import WaveSurfer from "wavesurfer.js";
import RegionPlugin from "wavesurfer.js/dist/plugin/wavesurfer.regions.min.js";

import Container from 'react-bootstrap/Container';
import Button from 'react-bootstrap/Button';
import Collapse from 'react-bootstrap/Collapse';
// import { Collapse, Button} from 'react-bootstrap';
// import {Button, Collapse} from 'react-bootstrap'

import 'bootstrap/dist/css/bootstrap.min.css';
require("./index.css");

// import { unregister } from "registerServiceWorker";

const audioURL = "/api/audio";
const fileURL = "/api/file";


function CollapseDiv(props) {
  const [open, setOpen] = useState(false);

  let className = "turn_" + props.name;

  let entries = [
    <div className='row turn-info-text'> Start: {props.startTime}</div>,
    <div className='row turn-info-text'> End: {props.endTime}</div>,
  ];

  if (props.trp) {
    entries.push(
      <div className='row turn-info-text'> TRP: {props.trp} </div>
    );
  }

  if (props.completion) {
    entries.push(
      <div className='row turn-info-text'> Completion: {props.completion}</div>
    );
    // entries.push(
    //   <div className='row turn-info-text'>
    //     Planned: {props.planned_utterance}
    //   </div>
    // );
  }

  return (
    <div>
      <Button onClick={() => setOpen(!open)} className={className} >
        {props.utterance}
      </Button>
      <Collapse in={open}>
        <div className='col'> {entries} </div>
      </Collapse>
    </div>
  );
}

class Dialog extends Component {
  constructor(props) {
    super(props);
    this.state = {
      dialog: null,
      showVad: false,
      showAsr: false,
      zoom: 0,
    };
  }

  // Waveform + AudioPlayer
  componentDidMount() {
    this.waveform = WaveSurfer.create({
      container: "#audioplayer",
      backend: "MediaElement",
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
      plugins: [RegionPlugin.create()],
    });
    this.waveform.load(audioURL);

    fetch(fileURL).then(response => response.json()).then((data) => {
      console.log(data);
      this.setState({dialog: data})
    })
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

  onClear() {
    let regs = this.waveform.regions.list;
    for (const region in regs) {
      console.log(region);
      console.log(regs[region]);
      regs[region].remove();
    }
  }

  removeRegion(id) {
    let regs = this.waveform.regions.list;
    for (const region in regs) {
      if (regs[region].id.includes(id+'Region')) {
        regs[region].remove();
      };
    }
  };

  onControlChange(name) {
    console.log(name)
    if (this.state.dialog !== null) {
      if (name === "vad") {
        if (this.state.showVad) {
          this.removeRegion(name)
          this.setState({showVad: false})
        } else {
          this.drawRegion(this.state.dialog.vad_ipu_on, this.state.dialog.vad_ipu_off, "#81c78430", 'vad')
          this.setState({showVad: true})
        };
      } else if (name === "asr"){
        if (this.state.showAsr) {
          this.removeRegion(name)
          this.setState({showAsr: false})
        } else {
          this.drawRegion(this.state.dialog.asr_on, this.state.dialog.asr_off, "#28309010", 'asr')
          this.setState({showAsr: true})
        };
      };
    }
  };

  getTurns() {
    const dialog = this.state.dialog;
    if (dialog !== null) {
      return (
        dialog.turns.map((turn, i) => {
          console.log('turn_' + i.toString())

          return (
            <li key={'turn_' + i.toString()}>
              <CollapseDiv 
                utterance={turn.utterance}
                name={turn.name}
                endTime={ turn.end_time }
                startTime={ turn.start_time }
                trp={turn.trp_at_eot}
                completion={turn.completion}
                planned_utterance={turn.planned_utterance}
                onTimeClick={this.onTimeClick}
              />
            </li>
          )
        })
      );
    }
  }

  render() {
    const turns = this.getTurns();
    return (
      <Container>
        <div id="audioplayer"></div>
        <div className="controls"> 
          <input type="range" min="50" max="500" style={{width: "400px"}} onChange={e => this.onZoom(e)}/>
          <br/>
          <input type="checkbox" value="showVad" checked={this.state.showVad} onChange={e => this.onControlChange("vad")}/>
          VAD
          <br/>
          <input type="checkbox" value="showAsr" checked={this.state.showAsr} onChange={e => this.onControlChange("asr")}/>
          ASR
        </div>
        <div className="dialog">
          <ol>{turns}</ol>
        </div>
        <div>
          <Button onClick={() => {this.onTimeClick(5)}}>
            Start: 5
          </Button>
        </div>
      </Container>
    );
  }
}

ReactDOM.render(<Dialog />, document.getElementById("root"));
