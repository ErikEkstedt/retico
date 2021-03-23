import React, { Component } from "react";
import Plot from 'react-plotly.js';

import { Container, ListGroup} from 'react-bootstrap';
const baseUrl = "/api/interaction"


function SingleAnnotation(props) {
  const width = 380;

  let grades_x = [];
  let grades_y = [];
  Object.entries(props.grades).forEach(([key, value]) => {
    grades_x.push(key)
    grades_y.push(value)
  })

  let anno_x = [];
  let anno_y = [];
  Object.entries(props.anno).forEach(([key, value]) => {
    anno_x.push(key)
    anno_y.push(value)
  })

  return (
    <div >
      <Plot
        data={[
          {x: grades_x, y: grades_y, type: 'bar'},
        ]}
        layout={{width: width, yaxis: {range: [1, 5]}, title: 'Grades'}}
      />
      <Plot
        data={[
          {x: anno_x, y: anno_y, type: 'bar', name: 'agent', nbinsx: props.bins},
        ]}
        layout={{width: width, title: 'Annotation'}}
      />
    </div>
  );
}


export default class TurnTaking extends Component {
  constructor(props) {
    super(props);
    this.state = { 
      tfo: null,
      fallback: null,
      omittedTurns: null,
      anno: null,
      turnOpportunity: null,
      trpInfo: null,
      responsivenessInterruption: null,
      interaction: props.interaction,
    };
  }

  componentDidMount() {
    fetch(baseUrl+'/tfo/'+this.state.interaction).then(response => response.json()).then((data) => {
      this.setState({tfo: data})
    });

    fetch(baseUrl+'/fallback/'+this.state.interaction).then(response => response.json()).then((data) => {
      this.setState({fallback: data.fallbacks})
    });

    fetch(baseUrl+'/omitted_turns/'+this.state.interaction).then(response => response.json()).then((data) => {
      this.setState({omittedTurns: data.omitted_turns})
    });

    fetch(baseUrl+'/anno/'+this.state.interaction).then(response => response.json()).then((data) => {
      this.setState({anno: data})
    });

    fetch(baseUrl+'/turn_opportunity/'+this.state.interaction).then(response => response.json()).then((data) => {
      this.setState({turnOpportunity: data})
    });

    fetch(baseUrl+'/trp_info/'+this.state.interaction).then(response => response.json()).then((data) => {
      this.setState({trpInfo: data})
    });

    fetch(baseUrl+'/responsiveness_and_interruption/'+this.state.interaction).then(response => response.json()).then((data) => {
      this.setState({responsivenessInterruption: data})
    });
  }

  getTRPInfo() {
    if (this.state.trpInfo === null){
      return 
    }

    const n_fallbacks = (this.state.fallback === null) ? 0 : this.state.fallback.length;
    const n_omitted = (this.state.omittedTurns === null) ? 0 : this.state.omittedTurns.length;

    let resp = 0 
    if (this.state.responsivenessInterruption !== null){
      resp =  + ", Intrr: " + this.state.responsivenessInterruption.error
      resp = <div>
        <p>Resp mean: {this.state.responsivenessInterruption.time_mean} </p>
        <p>Resp median: {this.state.responsivenessInterruption.time_median} </p>
        <p>Intrr: {this.state.responsivenessInterruption.error} </p>
        </div>
    }

    return (
      <Container>
        <ListGroup>
          <ListGroup.Item>User turns: {this.state.trpInfo.user_turns} </ListGroup.Item>
          <ListGroup.Item>N trp: {this.state.trpInfo.trp.length}</ListGroup.Item>
          <ListGroup.Item>N fallbacks: {Math.round(n_fallbacks*100/this.state.trpInfo.user_turns)}% ({n_fallbacks})</ListGroup.Item>
          <ListGroup.Item>Agent turns: {this.state.trpInfo.agent_turns}</ListGroup.Item>
          <ListGroup.Item>Interruptions: {this.state.trpInfo.agent_abort_ratio*100}% ({this.state.trpInfo.agent_aborted}). Interrupted agent turns where speech was emitted.</ListGroup.Item>
          <ListGroup.Item>Agent omitted: {n_omitted}. Turns without speech are omitted from the dialog (they never happened). </ListGroup.Item>
          <ListGroup.Item>{resp}</ListGroup.Item>
        </ListGroup>
        <hr/>
        <h2>TRP</h2>
        <p>The EOT prediction probability over all predictions.</p>
        <Plot
          data={[
            {x: this.state.trpInfo.trp, type: 'histogram', histnorm: 'probability', name: 'trp'},
          ]}
          layout= {{xaxis: {nticks: 10, title: 'TRP probability'}, yaxis: {title: '%'}}}
        />
      </Container>

    )
  }

  getTFO() {
    if (this.state.tfo === null){
      return 
    }
    return (
      <Container>
        <h2>TFO</h2>
        <p>Turn-Floor-Offset: the duration of silence prior a turn. </p>
        <Plot
          data={[
            {x: this.state.tfo.agent[2], type: 'histogram', histnorm: 'probability', name: 'agent', nbinsx: '20'},
            {x: this.state.tfo.user[2], type: 'histogram', histnorm: 'probability', name: 'user', nbinsx: '20'},
          ]}
          layout= {{xaxis: {title: 'time (s)'}, yaxis: {title: '%'}}}
        />
      </Container>
    )
  }

  getTurnOpportunity() {
    if (this.state.turnOpportunity === null){
      return 
    }

    return (
      <Container>
        <h2>Agent Turn Opportunities</h2>
        <p>The mutual silence (pauses or gaps) duration</p>
        <Plot
          data={[{
            x: this.state.turnOpportunity.pauses.duration, 
              type: 'histogram', 
              histnorm: 'probability', 
              name: 'pauses', 
              nbinsx: 10,
              xbins: { 
                end: 2.5, 
                  size: 0.2, 
                  start: 0,
              }},
            {
              x: this.state.turnOpportunity.shifts.duration, 
              type: 'histogram', 
              histnorm: 'probability', 
              name: 'shifts', 
              nbinsx: 10,
              xbins: { 
                end: 2.5, 
                size: 0.2, 
                start: 0,
              }},
          ]}
          layout= {{xaxis: {title: 'time (s)'}, yaxis: {title: '%'}}}
        />
      </Container>
    )
  }

  getAnno() {
    if (this.state.anno === null){
      return 
    }
    return (
      <Container>
        <h2>User Annotation</h2>
        <SingleAnnotation 
          grades={this.state.anno.grades}
          anno={this.state.anno.anno}
        />
      </Container>
    )
  }

  render () {
    const trp = this.getTRPInfo();
    const tfo = this.getTFO();
    const to = this.getTurnOpportunity();
    const anno = this.getAnno();
    return (
      <div>
        <h1> Global </h1>
        {trp}
        <hr/>
        {tfo}
        <hr/>
        {to}
        <hr/>
        {anno}
      </div>
    );
  }
}
